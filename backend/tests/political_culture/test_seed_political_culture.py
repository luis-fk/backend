import json
import shutil
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from political_culture.api.chatbot.tools import user_tools
from political_culture.api.word_counter.service import count_words
from political_culture.models import (
    IdeologiesDefinition,
    TextChunks,
    Texts,
    TextWordCount,
    Users,
)

DATABASES = pytest.mark.django_db(databases=["default", "political_culture_db"])
COMMAND_MODULE = "political_culture.management.commands.seed_political_culture"
SEED_DIR = settings.BASE_DIR / "political_culture" / "seed"
SEED: dict[str, Any] = json.loads(
    (SEED_DIR / "mare_livre.json").read_text(encoding="utf-8")
)
VECTOR: list[float] = json.loads(
    (SEED_DIR / "mare_livre_vector.json").read_text(encoding="utf-8")
)["vector"]
TEXT = "\n\n".join(SEED["paragraphs"])
REMOTE = {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": "x.proxy.rlwy.net",
    "PASSWORD": "secret-password",
}


def seed() -> None:
    call_command("seed_political_culture", stdout=StringIO())


def demo() -> Users:
    """demo's row in political culture's Users."""
    auth_user = get_user_model().objects.get(username="demo")
    return Users.objects.get(auth_user_id=auth_user.pk)


@DATABASES
def test_the_seed_gives_demo_the_ideology_and_a_ticked_library_text() -> None:
    seed()

    auth_demo = get_user_model().objects.get(username="demo")
    assert auth_demo.is_active
    assert auth_demo.is_staff and auth_demo.is_superuser
    assert auth_demo.check_password("demo")
    user = Users.objects.get(auth_user_id=auth_demo.pk)
    assert user.active
    ideology = IdeologiesDefinition.objects.get()
    assert (ideology.ideology, ideology.definition) == (
        SEED["ideology"],
        SEED["definition"],
    )
    text = Texts.objects.get()
    assert (text.title, text.author, text.ideology, text.content_description) == (
        SEED["title"],
        SEED["author"],
        SEED["ideology"],
        SEED["summary"],
    )
    assert text.text == TEXT
    assert (text.user_id, text.user_submitted_text, text.file_hash) == (
        user.pk,
        False,
        None,
    )
    assert list(text.selected_by.all()) == [user]


@DATABASES
def test_a_blocked_demo_can_use_the_app_again() -> None:
    auth_demo = get_user_model().objects.create_user(username="demo", is_active=False)
    Users.objects.create(auth_user_id=auth_demo.pk, active=False)

    seed()

    auth_demo.refresh_from_db()
    assert auth_demo.is_active and auth_demo.is_superuser
    assert auth_demo.check_password("demo")
    assert demo().active


@DATABASES
def test_the_output_says_how_to_log_in() -> None:
    out = StringIO()

    call_command("seed_political_culture", stdout=out)

    assert (
        "political_culture: log in as demo, with the password demo in the admin"
        in out.getvalue()
    )


@DATABASES
def test_the_word_count_comes_ready_with_the_file_words() -> None:
    seed()

    word_count = TextWordCount.objects.get(text__title=SEED["title"])
    words, total = count_words(TEXT)
    counts = dict(words)
    assert word_count.total_word_count == total
    assert word_count.word_frequencies == {word: counts[word] for word in SEED["words"]}


@DATABASES
def test_the_text_is_one_chunk_with_the_file_vector() -> None:
    seed()

    chunk = TextChunks.objects.get(text__title=SEED["title"])
    assert chunk.chunk_text == TEXT
    assert len(chunk.vector) == 1536
    assert chunk.vector.tolist() == VECTOR


@DATABASES
def test_the_chat_of_demo_reads_the_text() -> None:
    seed()
    text = Texts.objects.get()
    tools = user_tools(demo().pk)

    assert tools.library_texts.invoke({}) == [
        (text.pk, SEED["title"], SEED["ideology"], SEED["author"], SEED["summary"])
    ]
    assert tools.word_count.invoke({"text_id": text.pk}) == (
        TextWordCount.objects.get().word_frequencies
    )


@DATABASES
def test_running_it_again_replaces_only_what_it_made() -> None:
    seed()
    user = demo()
    other_ideology = IdeologiesDefinition.objects.create(
        ideology="Outra", definition="Outra ideia."
    )
    someone = Users.objects.create(auth_user_id=user.auth_user_id + 1)
    other_text = Texts.objects.create(user=someone, title="Outro texto", text="Outro.")
    other_text.selected_by.add(user)

    seed()

    ideology = IdeologiesDefinition.objects.get(ideology=SEED["ideology"])
    assert set(IdeologiesDefinition.objects.all()) == {ideology, other_ideology}
    text = Texts.objects.get(title=SEED["title"])
    assert set(Texts.objects.all()) == {text, other_text}
    assert TextChunks.objects.get().text_id == text.pk
    assert TextWordCount.objects.get().text_id == text.pk
    assert set(user.selected_texts.all()) == {text, other_text}


@DATABASES
def test_a_word_missing_from_the_text_stops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    edited = {**SEED, "words": [*SEED["words"], "dragão"]}
    (tmp_path / "mare_livre.json").write_text(json.dumps(edited), encoding="utf-8")
    shutil.copy(SEED_DIR / "mare_livre_vector.json", tmp_path)
    monkeypatch.setattr(f"{COMMAND_MODULE}.SEED_DIR", tmp_path)

    with pytest.raises(CommandError, match="dragão"):
        seed()

    assert not IdeologiesDefinition.objects.exists()
    assert not Texts.objects.exists()


@DATABASES
def test_it_refuses_a_remote_database_before_writing_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    databases = {**settings.DATABASES, "political_culture_db": REMOTE}
    monkeypatch.setattr(settings, "DATABASES", databases)

    with pytest.raises(CommandError) as error:
        seed()

    assert "political_culture_db (x.proxy.rlwy.net)" in str(error.value)
    assert "secret-password" not in str(error.value)
    assert not get_user_model().objects.filter(username="demo").exists()
    assert not Users.objects.exists()
    assert not IdeologiesDefinition.objects.exists()
    assert not Texts.objects.exists()
