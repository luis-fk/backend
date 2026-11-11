import json
from pathlib import Path
from typing import Any, TypedDict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction

from political_culture.api.word_counter.service import count_words
from political_culture.models import (
    IdeologiesDefinition,
    TextChunks,
    Texts,
    TextWordCount,
    Users,
)

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
DEMO_USERNAME = "demo"
# An empty host, or a path, is PostgreSQL's socket on this machine.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


class Seed(TypedDict):
    """mare_livre.json: a made-up ideology, a library text about it and the words
    its word count keeps."""

    ideology: str
    definition: str
    title: str
    author: str
    summary: str
    paragraphs: list[str]
    words: list[str]


class Command(BaseCommand):
    help = (
        "Writes political culture's sample data to the local databases: the person "
        "demo, an ideology and a library text demo ticked. Running it again "
        "replaces them."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        require_local_databases()
        seed: Seed = read_seed_file("mare_livre.json")
        vector: list[float] = read_seed_file("mare_livre_vector.json")["vector"]
        demo = seed_demo()
        with transaction.atomic(using=router.db_for_write(Texts)):
            replace_ideology(seed)
            replace_text(seed, vector, demo)
        self.stdout.write(f"political_culture: {DEMO_USERNAME} can use the app")
        self.stdout.write(f"political_culture: ideology {seed['ideology']}")
        self.stdout.write(
            f"political_culture: library text {seed['title']}, ticked by "
            f"{DEMO_USERNAME}"
        )


def require_local_databases() -> None:
    """The seed is for this machine's databases, and backend/.env may hold the
    production URLs. The app's own copy of backend/local_databases.py, since the
    apps share no code."""
    remote: list[str] = []
    for alias, config in settings.DATABASES.items():
        host = config.get("HOST") or ""
        if "sqlite" in config["ENGINE"] or host in LOCAL_HOSTS or host.startswith("/"):
            continue
        remote.append(f"{alias} ({host})")
    if remote:
        raise CommandError(
            f"Not local: {', '.join(remote)}. The seed only writes to the local "
            "databases; check backend/.env."
        )


def read_seed_file(name: str) -> Any:
    return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))


def seed_demo() -> Users:
    """demo, active in auth and in political culture. The site logs in by name, so a
    new demo gets no password, like a person the admin adds without one."""
    demo, created = get_user_model().objects.get_or_create(username=DEMO_USERNAME)
    if created:
        demo.set_unusable_password()
    demo.is_active = True
    demo.save()
    user, _ = Users.objects.update_or_create(
        auth_user_id=demo.pk, defaults={"active": True}
    )
    return user


def replace_ideology(seed: Seed) -> None:
    IdeologiesDefinition.objects.filter(ideology=seed["ideology"]).delete()
    IdeologiesDefinition.objects.create(
        ideology=seed["ideology"], definition=seed["definition"]
    )


def replace_text(seed: Seed, vector: list[float], demo: Users) -> None:
    """The library text, ticked by demo so the chat uses it, with its word count and
    a single chunk: the text fits one chunk of the uploads' splitter, and the vector
    was made from all of it. The text of an earlier run goes first, and its chunk,
    word count and ticks go with it."""
    text = "\n\n".join(seed["paragraphs"])
    frequencies, total = word_frequencies(text, seed["words"])
    Texts.objects.filter(title=seed["title"], user_submitted_text=False).delete()
    library_text = Texts.objects.create(
        user=demo,
        title=seed["title"],
        author=seed["author"],
        ideology=seed["ideology"],
        text=text,
        content_description=seed["summary"],
        user_submitted_text=False,
    )
    library_text.selected_by.add(demo)
    TextWordCount.objects.create(
        text=library_text, total_word_count=total, word_frequencies=frequencies
    )
    TextChunks.objects.create(text=library_text, chunk_text=text, vector=vector)


def word_frequencies(text: str, words: list[str]) -> tuple[dict[str, int], int]:
    """The file's words with the counts the word counter gives, and the text's
    total. An upload has the model pick its words; the seed has them in the file."""
    sorted_counts, total = count_words(text)
    counts = dict(sorted_counts)
    missing = [word for word in words if word not in counts]
    if missing:
        raise CommandError(f"Not in the text's word count: {', '.join(missing)}.")
    return {word: counts[word] for word in words}, total
