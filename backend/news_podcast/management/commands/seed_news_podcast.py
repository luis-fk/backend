import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import models, router, transaction

from news_podcast.models import Feed, PodcastSettings

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
# An empty host, or a path, is PostgreSQL's socket on this machine.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


class Command(BaseCommand):
    help = (
        "Fills news_podcast's database from news_podcast/seed/: the settings row when "
        "there is none and the feeds when the list is empty, never changing a row. "
        "Only local databases or, with --production, the one shown after you confirm."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--production",
            action="store_true",
            help="Shows news_podcast_db's host and asks before writing to it.",
        )

    def handle(self, *args: Any, production: bool, **options: Any) -> None:
        podcast_settings = settings_row(read_seed_file("settings.json"))
        feeds = feed_rows(read_seed_file("feeds.json"))
        database = router.db_for_write(PodcastSettings)
        if production:
            self.confirm(database)
        else:
            require_local_databases()
        with transaction.atomic(using=database):
            self.seed_settings(podcast_settings)
            self.seed_feeds(feeds)

    def confirm(self, database: str) -> None:
        config = settings.DATABASES[database]
        self.stdout.write(f"The seed will write to {database}: {address(config)}")
        if input("Type yes to go on: ") != "yes":
            raise CommandError("Nothing was written.")

    def seed_settings(self, podcast_settings: PodcastSettings) -> None:
        if PodcastSettings.objects.exists():
            self.stdout.write(
                "news_podcast: the settings row already exists; left as it was"
            )
            return
        podcast_settings.save()
        self.stdout.write("news_podcast: settings created from seed/settings.json")

    def seed_feeds(self, feeds: list[Feed]) -> None:
        if Feed.objects.exists():
            self.stdout.write("news_podcast: the feed list isn't empty; left as it was")
            return
        Feed.objects.bulk_create(feeds)
        self.stdout.write(
            f"news_podcast: {len(feeds)} feeds created from seed/feeds.json"
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


def address(config: Mapping[str, Any]) -> str:
    """Where a database is, as host:port/name, without its user and password."""
    host = config.get("HOST") or "local socket"
    port = f":{config['PORT']}" if config.get("PORT") else ""
    return f"{host}{port}/{config.get('NAME', '')}"


def read_seed_file(name: str) -> Any:
    try:
        return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CommandError(f"seed/{name} isn't valid JSON: {error}") from error


def settings_row(values: Mapping[str, Any]) -> PodcastSettings:
    where = "seed/settings.json"
    check_keys(values, PodcastSettings, where)
    podcast_settings = PodcastSettings(**values)
    check_values(podcast_settings, where)
    return podcast_settings


def feed_rows(entries: list[Mapping[str, Any]]) -> list[Feed]:
    feeds: list[Feed] = []
    for number, values in enumerate(entries, start=1):
        where = f"seed/feeds.json, entry {number}"
        check_keys(values, Feed, where)
        feed = Feed(**values)
        check_values(feed, where)
        feeds.append(feed)
    urls = Counter(feed.url for feed in feeds)
    if repeated := [url for url, count in urls.items() if count > 1]:
        raise CommandError(f"seed/feeds.json repeats {', '.join(repeated)}")
    return feeds


def check_keys(
    values: Mapping[str, Any], model: type[models.Model], where: str
) -> None:
    """A seed file holds every field the admin edits, and nothing else."""
    fields = [
        field.name
        for field in model._meta.concrete_fields
        if field.editable and not field.primary_key
    ]
    if missing := [name for name in fields if name not in values]:
        raise CommandError(f"{where} lacks {', '.join(missing)}")
    if unknown := [name for name in values if name not in fields]:
        raise CommandError(f"{where} has unknown fields: {', '.join(unknown)}")


def check_values(row: models.Model, where: str) -> None:
    """The admin's checks. Not validate_unique: on a seeded database the file's URLs
    are already in the list, and feed_rows checks the file's own repeats."""
    try:
        row.full_clean(validate_unique=False)
    except ValidationError as error:
        problems = "; ".join(
            f"{name}: {' '.join(messages)}"
            for name, messages in error.message_dict.items()
        )
        raise CommandError(f"{where}: {problems}") from error
