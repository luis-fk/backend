import asyncio
import hashlib
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from pytest_django import Settings

from political_culture.api.texts import serializers, service
from political_culture.api.texts.routing import websocket_urlpatterns
from political_culture.api.word_counter import service as word_counter
from political_culture.api.word_counter.schemas import (
    TitleAndAuthorSchema,
    WordCount,
    WordFrequencySquema,
)
from political_culture.models import TextChunks, Texts, TextWordCount, Users
from tests.api_tokens import bearer, make_token, user_token

APP = "political-culture"
DATABASES = pytest.mark.django_db(databases=["default", "political_culture_db"])
THREAD = "political_culture.api.texts.service.threading.Thread"
UPLOAD_ID = "2f6d9c1a-5b7e-4c3d-8a9f-0e1b2c3d4e5f"

INFO = TitleAndAuthorSchema(
    reasoning="The cover names both.",
    title="Manifesto",
    author="Fulano de Tal",
    content_description="Um panfleto político.",
)
PICKED = WordFrequencySquema(
    reasoning="Political terms.",
    words_list=[WordCount(word="liberdade", count=2)],
)


def tiny_pdf(text: str) -> bytes:
    """A one-page PDF built by hand, the smallest one PyPDF reads text from."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return pdf


def auth(user_id: int = 7) -> dict[str, str]:
    return bearer(user_token(APP, str(user_id)))


def upload(client: Client, content: bytes, name: str = "texto.pdf") -> Any:
    pdf = SimpleUploadedFile(name, content, content_type="application/pdf")
    return client.post(
        "/api/political-culture/texts",
        {"content": pdf, "upload_id": UPLOAD_ID},
        headers=auth(),
    )


def library_user(auth_user_id: int = 1) -> Users:
    return Users.objects.create(auth_user_id=auth_user_id)


def library_text(user: Users, title: str, **fields: Any) -> Texts:
    return Texts.objects.create(user=user, title=title, text=f"{title}…", **fields)


def pages(*contents: str) -> Any:
    """Stands in for PyPDF, reading these pages from any file."""
    loader = MagicMock()
    loader.return_value.load.return_value = [Document(page_content=c) for c in contents]
    return patch.object(word_counter, "PyPDFLoader", loader)


@pytest.fixture
def models() -> Iterator[MagicMock]:
    """The embeddings and the two model calls of add_pdf_text, without OpenAI."""
    with (
        patch.object(word_counter, "OpenAIEmbeddings") as embeddings,
        patch.object(word_counter, "extract_text_info", return_value=INFO) as info,
        patch.object(word_counter, "word_picker", return_value=PICKED) as picker,
    ):
        embeddings.return_value.embed_documents.side_effect = lambda texts: [
            [0.5] * 1536 for _ in texts
        ]
        yield MagicMock(embeddings=embeddings, info=info, picker=picker)


@pytest.fixture(autouse=True)
def nothing_being_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test's uploads never really get read, so each test starts with none."""
    monkeypatch.setattr(service, "_reading", set())


@pytest.fixture
def temp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where the upload copies go, so a test can see whether one was left behind."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


# The list


@DATABASES
def test_the_list_is_the_library_newest_first(client: Client) -> None:
    user = library_user()
    library_text(user, "Primeiro")
    library_text(user, "Colado no chat", user_submitted_text=True)
    library_text(user, "Segundo")

    response = client.get("/api/political-culture/texts", headers=auth())

    assert [text["title"] for text in response.json()] == ["Segundo", "Primeiro"]


@DATABASES
def test_the_list_says_who_added_each_text_and_leaves_out_the_text(
    client: Client,
) -> None:
    fulano = get_user_model().objects.create(username="fulano")
    manifesto = library_text(
        library_user(fulano.id),
        "Manifesto",
        author="Fulano de Tal",
        content_description="Um panfleto.",
    )
    TextWordCount.objects.create(
        text=manifesto, total_word_count=120, word_frequencies={}
    )
    orphan = library_text(library_user(fulano.id + 1), "Sem dono")

    response = client.get("/api/political-culture/texts", headers=auth())

    assert response.json() == [
        {
            "id": orphan.id,
            "title": "Sem dono",
            "author": None,
            "description": None,
            "word_count": None,
            "added_by": None,
            "selected": False,
        },
        {
            "id": manifesto.id,
            "title": "Manifesto",
            "author": "Fulano de Tal",
            "description": "Um panfleto.",
            "word_count": 120,
            "added_by": "fulano",
            "selected": False,
        },
    ]


# Each user's ticks


def tick(client: Client, user: Users, text_id: int, body: dict[str, Any]) -> Any:
    return client.put(
        f"/api/political-culture/texts/{text_id}/selection",
        body,
        content_type="application/json",
        headers=auth(user.id),
    )


@DATABASES
def test_users_tick_and_untick_texts_for_their_analyses(client: Client) -> None:
    me = library_user(1)
    text = library_text(library_user(2), "Manifesto")

    assert tick(client, me, text.id, {"selected": True}).status_code == 204
    assert list(text.selected_by.all()) == [me]
    assert tick(client, me, text.id, {"selected": True}).status_code == 204
    assert list(text.selected_by.all()) == [me]

    assert tick(client, me, text.id, {"selected": False}).status_code == 204
    assert not text.selected_by.exists()


@DATABASES
def test_the_list_shows_only_the_users_own_ticks(client: Client) -> None:
    me, other = library_user(1), library_user(2)
    mine = library_text(other, "Meu")
    theirs = library_text(other, "Do outro")
    mine.selected_by.add(me)
    theirs.selected_by.add(other)

    response = client.get("/api/political-culture/texts", headers=auth(me.id))

    assert {text["title"]: text["selected"] for text in response.json()} == {
        "Meu": True,
        "Do outro": False,
    }


@DATABASES
def test_only_library_texts_can_be_ticked(client: Client) -> None:
    me = library_user(1)
    pasted = library_text(me, "Colado no chat", user_submitted_text=True)

    assert tick(client, me, pasted.id, {"selected": True}).status_code == 404
    assert tick(client, me, pasted.id + 1, {"selected": True}).status_code == 404
    assert not pasted.selected_by.exists()


@DATABASES
@pytest.mark.parametrize("body", [{}, {"selected": "talvez"}], ids=["none", "text"])
def test_a_tick_needs_true_or_false(client: Client, body: dict[str, Any]) -> None:
    text = library_text(library_user(2), "Manifesto")

    assert tick(client, library_user(1), text.id, body).status_code == 400
    assert not text.selected_by.exists()


# The upload


@DATABASES
def test_a_pdf_is_read_in_the_background_from_a_copy(
    client: Client, temp_dir: Path
) -> None:
    content = tiny_pdf("Liberdade")

    with patch(THREAD) as thread:
        response = upload(client, content)

    assert response.status_code == 202
    assert thread.call_args.kwargs["target"] is service._read_in_background
    path, file_hash, user_id, upload_id = thread.call_args.kwargs["args"]
    assert response.json() == {"upload_id": UPLOAD_ID}
    assert upload_id == UPLOAD_ID
    assert Path(path).read_bytes() == content
    assert file_hash == hashlib.sha256(content).hexdigest()
    assert user_id == 7
    thread.return_value.start.assert_called_once()


@DATABASES
@pytest.mark.parametrize("upload_id", [None, "upload-1"], ids=["none", "not a UUID"])
def test_an_upload_needs_the_id_its_result_will_carry(
    client: Client, temp_dir: Path, upload_id: str | None
) -> None:
    data: dict[str, Any] = {"content": SimpleUploadedFile("t.pdf", tiny_pdf("Lei"))}
    if upload_id:
        data["upload_id"] = upload_id

    with patch(THREAD) as thread:
        response = client.post("/api/political-culture/texts", data, headers=auth())

    assert response.status_code == 400
    thread.assert_not_called()
    assert list(temp_dir.iterdir()) == []


@DATABASES
def test_a_pdf_being_read_is_refused_until_its_reading_ends(
    client: Client, temp_dir: Path
) -> None:
    content = tiny_pdf("Liberdade")

    with patch(THREAD) as thread:
        assert upload(client, content).status_code == 202
        assert upload(client, content).status_code == 409
    assert len(list(temp_dir.iterdir())) == 1

    with (
        patch.object(service, "read_upload", return_value={"status": "failed"}),
        patch.object(service, "notify_uploader"),
        patch.object(service, "connections"),
    ):
        service._read_in_background(*thread.call_args.kwargs["args"])

    with patch(THREAD):
        assert upload(client, content).status_code == 202


@DATABASES
@pytest.mark.parametrize(
    "content",
    [b"just some text", b"", b"x" * serializers.PDF_HEADER_SEARCH + b"%PDF-1.4"],
    ids=["text file", "empty file", "header past the first kilobyte"],
)
def test_a_file_that_is_not_a_pdf_is_refused(
    client: Client, temp_dir: Path, content: bytes
) -> None:
    with patch(THREAD) as thread:
        response = upload(client, content)

    assert response.status_code == 400
    thread.assert_not_called()
    assert list(temp_dir.iterdir()) == []


@DATABASES
def test_a_pdf_over_the_limit_is_refused(
    client: Client, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = tiny_pdf("Liberdade")
    monkeypatch.setattr(serializers, "MAX_PDF_BYTES", len(content) - 1)

    with patch(THREAD) as thread:
        response = upload(client, content)

    assert response.status_code == 400
    thread.assert_not_called()


@DATABASES
def test_a_pdf_already_in_the_library_is_refused_and_its_copy_deleted(
    client: Client, temp_dir: Path
) -> None:
    content = tiny_pdf("Liberdade")
    library_text(
        library_user(), "Manifesto", file_hash=hashlib.sha256(content).hexdigest()
    )

    with patch(THREAD) as thread:
        response = upload(client, content)

    assert response.status_code == 409
    thread.assert_not_called()
    assert list(temp_dir.iterdir()) == []


# Reading a PDF into the library


@DATABASES
def test_a_pdf_is_saved_with_its_chunks_info_and_word_count(
    models: MagicMock, tmp_path: Path
) -> None:
    path = tmp_path / "manifesto.pdf"
    path.write_bytes(tiny_pdf("Liberdade igualdade fraternidade"))

    text = word_counter.add_pdf_text(str(path), "hash", library_user().id)

    text.refresh_from_db()
    assert "Liberdade igualdade fraternidade" in text.text
    assert (text.title, text.author, text.content_description, text.file_hash) == (
        "Manifesto",
        "Fulano de Tal",
        "Um panfleto político.",
        "hash",
    )
    assert text.user_submitted_text is False
    chunk = text.chunks.get()
    assert "Liberdade igualdade fraternidade" in (chunk.chunk_text or "")
    assert len(chunk.vector) == 1536
    assert text.analysis.word_frequencies == {"liberdade": 2}
    assert text.analysis.total_word_count == 3
    assert not text.selected_by.exists()


@DATABASES
def test_a_failure_while_saving_leaves_nothing_behind(models: MagicMock) -> None:
    user = library_user()

    with (
        pages("Liberdade igualdade fraternidade"),
        patch.object(TextWordCount.objects, "create", side_effect=RuntimeError),
        pytest.raises(RuntimeError),
    ):
        word_counter.add_pdf_text("manifesto.pdf", "hash", user.id)

    assert not Texts.objects.exists()
    assert not TextChunks.objects.exists()


@DATABASES
def test_a_pdf_without_text_is_refused_before_any_model_call(
    models: MagicMock,
) -> None:
    with pages("", "  \n"), pytest.raises(word_counter.NoText):
        word_counter.add_pdf_text("scan.pdf", "hash", library_user().id)

    models.embeddings.assert_not_called()
    models.info.assert_not_called()
    assert not Texts.objects.exists()


@DATABASES
def test_halves_of_surrogate_pairs_do_not_break_the_save(models: MagicMock) -> None:
    # PyPDF can split a math font's character into two halves, or keep only one.
    with pages("x\ud835\udc00y \ud835 z"):
        text = word_counter.add_pdf_text("math.pdf", "hash", library_user().id)

    text.refresh_from_db()
    assert text.text == "x\U0001d400y \ufffd z"


@DATABASES
def test_a_long_title_and_author_are_cut_to_their_columns(models: MagicMock) -> None:
    models.info.return_value = INFO.model_copy(
        update={"title": "T" * 600, "author": "A" * 300}
    )

    with pages("Liberdade"):
        text = word_counter.add_pdf_text("livro.pdf", "hash", library_user().id)

    text.refresh_from_db()
    assert (len(text.title or ""), len(text.author or "")) == (500, 255)


@DATABASES
def test_nul_characters_are_dropped_from_the_text(models: MagicMock) -> None:
    with pages("Liber\x00dade"):
        text = word_counter.add_pdf_text("manifesto.pdf", "hash", library_user().id)

    assert text.text == "Liberdade"
    assert text.chunks.get().chunk_text == "Liberdade"


def test_the_word_picker_gets_only_the_most_frequent_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []

    def pick(prompt: Any) -> dict[str, Any]:
        prompts.append(prompt.to_string())
        return PICKED.model_dump()

    class PickerModel:
        def with_structured_output(self, **_kwargs: Any) -> RunnableLambda[Any, Any]:
            return RunnableLambda(pick)

    monkeypatch.setattr(word_counter, "llm_4", PickerModel())
    words = [(f"palavra{n}", 10_000 - n) for n in range(5000)]

    word_counter.word_picker(words, "Um livro.")

    assert f"'palavra{word_counter.MAX_PICKER_WORDS - 1}'" in prompts[0]
    assert f"'palavra{word_counter.MAX_PICKER_WORDS}'" not in prompts[0]


# How an upload ends


def test_a_finished_upload_reports_its_text_and_deletes_the_copy(
    tmp_path: Path,
) -> None:
    path = tmp_path / "copy.pdf"
    path.write_bytes(b"%PDF-")

    with patch.object(service, "add_pdf_text", return_value=MagicMock(id=3)):
        result = service.read_upload(str(path), "hash", 7, "upload")

    assert result == {"upload_id": "upload", "status": "ready", "text_id": 3}
    assert not path.exists()


@pytest.mark.parametrize(
    ("error", "reason"),
    [(word_counter.NoText(), "no_text"), (RuntimeError("OpenAI is down"), "error")],
    ids=["no text", "any other error"],
)
def test_a_failed_upload_reports_why_and_deletes_the_copy(
    tmp_path: Path, error: Exception, reason: str
) -> None:
    path = tmp_path / "copy.pdf"
    path.write_bytes(b"%PDF-")

    with patch.object(service, "add_pdf_text", side_effect=error):
        result = service.read_upload(str(path), "hash", 7, "upload")

    assert result == {"upload_id": "upload", "status": "failed", "reason": reason}
    assert not path.exists()


# The texts socket


@pytest.fixture
def in_memory_channel_layer(settings: Settings) -> None:
    """The socket joins a group on the channel layer; keep it off Redis."""
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }


def texts_socket(user_id: int, token: str) -> WebsocketCommunicator:
    return WebsocketCommunicator(
        URLRouter(websocket_urlpatterns),
        f"/ws/political-culture/texts/{user_id}",
        subprotocols=["bearer", token],
    )


@pytest.mark.usefixtures("in_memory_channel_layer")
def test_the_uploader_hears_how_the_upload_ended() -> None:
    result: service.UploadResult = {
        "upload_id": "upload",
        "status": "ready",
        "text_id": 3,
    }

    async def listen() -> tuple[Any, Any]:
        socket = texts_socket(7, user_token(APP, "7"))
        _, subprotocol = await socket.connect()
        await sync_to_async(service.notify_uploader)(7, result)
        message = await socket.receive_json_from()
        await socket.disconnect()
        return subprotocol, message

    assert asyncio.run(listen()) == ("bearer", result)


@pytest.mark.usefixtures("in_memory_channel_layer")
def test_other_users_do_not_hear_about_the_upload() -> None:
    async def listen() -> bool:
        socket = texts_socket(8, user_token(APP, "8"))
        await socket.connect()
        await sync_to_async(service.notify_uploader)(7, {"status": "ready"})
        heard_nothing: bool = await socket.receive_nothing()
        await socket.disconnect()
        return heard_nothing

    assert asyncio.run(listen())


@pytest.mark.usefixtures("in_memory_channel_layer")
@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "8", "app": APP, "purpose": "user"},
        {"sub": "7", "app": "plants", "purpose": "user"},
    ],
    ids=["another user", "another app"],
)
def test_the_texts_socket_refuses_other_tokens(claims: dict[str, str]) -> None:
    async def connect() -> bool:
        socket = texts_socket(7, make_token(**claims))
        connected, _ = await socket.connect()
        await socket.disconnect()
        return bool(connected)

    assert not asyncio.run(connect())
