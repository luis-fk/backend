import hashlib
import logging
import os
import tempfile
import threading
import uuid
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
    # Whether the text is in this user's analyses.
    selected: bool


class DuplicateText(Exception):
    """The PDF is already in the library."""


def library_texts(user_id: int) -> list[LibraryText]:
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
    selected = set(
        Texts.objects.filter(selected_by__id=user_id).values_list("id", flat=True)
    )
    return [
        LibraryText(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            description=row["description"],
            word_count=row["word_count"],
            added_by=names.get(row["auth_user_id"]),
            selected=row["id"] in selected,
        )
        for row in rows
    ]


def select_text(user_id: int, text_id: int, selected: bool) -> None:
    """Ticks or unticks a library text for the user's analyses. Raises
    Texts.DoesNotExist for an unknown text or one pasted in the chat."""
    text = Texts.objects.get(id=text_id, user_submitted_text=False)
    if selected:
        text.selected_by.add(user_id)
    else:
        text.selected_by.remove(user_id)


def start_upload(pdf: UploadedFile, user_id: int) -> str:
    """Refuses a PDF already in the library, then reads it in the background, since
    a book takes minutes. Returns the upload's id, which its result carries."""
    path, file_hash = _save_copy(pdf)
    if Texts.objects.filter(file_hash=file_hash).exists():
        os.unlink(path)
        raise DuplicateText()

    upload_id = uuid.uuid4().hex
    threading.Thread(
        target=_read_in_background,
        args=(path, file_hash, user_id, upload_id),
        daemon=True,
    ).start()
    return upload_id


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


def _read_in_background(
    path: str, file_hash: str, user_id: int, upload_id: str
) -> None:
    try:
        result = read_upload(path, file_hash, user_id, upload_id)
    finally:
        # The thread's own connections: Django only closes those of a request.
        connections.close_all()
    notify_uploader(user_id, result)
