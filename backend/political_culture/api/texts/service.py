import hashlib
import logging
import os
import tempfile
import threading
from typing import TypedDict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db import connections
from django.db.models import F

from political_culture.api.word_counter.service import NoText, add_pdf_text
from political_culture.models import Texts

logger = logging.getLogger(__name__)

# What the user's texts socket gets when an upload ends: "ready" with the text's id,
# or "failed" with a reason, "no_text" or "error".
UploadResult = dict[str, str | int]


class LibraryText(TypedDict):
    id: int
    title: str | None
    author: str | None
    description: str | None
    word_count: int | None
    added_by: str | None


class DuplicateText(Exception):
    """The PDF is already in the library, or being read."""


# The hashes of the PDFs being read, so the same file sent again before its reading
# ends isn't read and paid for twice. One process serves the API, so memory is enough.
_reading: set[str] = set()
_reading_lock = threading.Lock()


def library_texts() -> list[LibraryText]:
    """The library, newest first, without the texts themselves, which can be books."""
    rows = list(
        Texts.objects.filter(user_submitted_text=False)
        .order_by("-id")
        .values(
            "id",
            "title",
            "author",
            description=F("content_description"),
            word_count=F("analysis__total_word_count"),
            auth_user_id=F("user__auth_user_id"),
        )
    )
    # The names live in the default database, so they can't come in the same query.
    names = dict(
        get_user_model()
        .objects.filter(id__in={row["auth_user_id"] for row in rows})
        .values_list("id", "username")
    )
    return [
        LibraryText(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            description=row["description"],
            word_count=row["word_count"],
            added_by=names.get(row["auth_user_id"]),
        )
        for row in rows
    ]


def start_upload(pdf: UploadedFile, user_id: int, upload_id: str) -> None:
    """Refuses a PDF that is in the library or being read, then reads it in the
    background, since a book takes minutes. The result carries upload_id, which the
    page picks before sending, so it can't arrive before the page knows the id."""
    path, file_hash = _save_copy(pdf)
    try:
        _claim(file_hash)
    except BaseException:
        os.unlink(path)
        raise

    threading.Thread(
        target=_read_in_background,
        args=(path, file_hash, user_id, upload_id),
        daemon=True,
    ).start()


def read_upload(
    path: str, file_hash: str, user_id: int, upload_id: str
) -> UploadResult:
    """Reads the PDF into the library and deletes the copy. The result says how it
    ended instead of raising."""
    try:
        text = add_pdf_text(path, file_hash, user_id)
    except NoText:
        return {"upload_id": upload_id, "status": "failed", "reason": "no_text"}
    except Exception:
        logger.exception(f"Upload {upload_id} of user {user_id} failed")
        return {"upload_id": upload_id, "status": "failed", "reason": "error"}
    finally:
        os.unlink(path)
    return {"upload_id": upload_id, "status": "ready", "text_id": text.id}


def notify_uploader(user_id: int, result: UploadResult) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"texts_{user_id}", {"type": "upload.result", "result": result}
    )


def _save_copy(pdf: UploadedFile) -> tuple[str, str]:
    """A copy of the upload, which Django deletes when the request ends, and its
    SHA-256."""
    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as copy:
        for chunk in pdf.chunks():
            digest.update(chunk)
            copy.write(chunk)
    return copy.name, digest.hexdigest()


def _claim(file_hash: str) -> None:
    with _reading_lock:
        if file_hash in _reading or Texts.objects.filter(file_hash=file_hash).exists():
            raise DuplicateText()
        _reading.add(file_hash)


def _read_in_background(
    path: str, file_hash: str, user_id: int, upload_id: str
) -> None:
    try:
        result = read_upload(path, file_hash, user_id, upload_id)
    finally:
        with _reading_lock:
            _reading.discard(file_hash)
        # The thread's own connections: Django only closes those of a request.
        connections.close_all()
    notify_uploader(user_id, result)
