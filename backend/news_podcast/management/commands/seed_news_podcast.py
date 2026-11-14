import json
import math
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import models, router, transaction

from news_podcast.models import Area, Feed, PodcastSettings, Topic

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
# An empty host, or a path, is PostgreSQL's socket on this machine.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


class Command(BaseCommand):
    help = (
        "Fills news_podcast's database from news_podcast/seed/: the settings row when "
        "there is none, and the feeds and the lesson catalog when they are empty, "
        "never changing a row. Only local databases or, with --production, the one "
        "shown after you confirm."
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
        catalog = catalog_rows(read_seed_file("catalog.json"))
        database = router.db_for_write(PodcastSettings)
        if production:
            self.confirm(database)
        else:
            require_local_databases()
        with transaction.atomic(using=database):
            self.seed_settings(podcast_settings)
            self.seed_feeds(feeds)
            self.seed_catalog(catalog)

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

    def seed_catalog(self, catalog: list[tuple[Area, list[Topic]]]) -> None:
        if Area.objects.exists():
            self.stdout.write("news_podcast: the catalog isn't empty; left as it was")
            return
        for area, topics in catalog:
            area.save()
            for topic in topics:
                topic.area = area
        Topic.objects.bulk_create([topic for _, topics in catalog for topic in topics])
        count = sum(len(topics) for _, topics in catalog)
        self.stdout.write(
            f"news_podcast: {len(catalog)} areas and {count} topics created from "
            "seed/catalog.json"
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
    except (OSError, ValueError) as error:
        raise CommandError(f"seed/{name} can't be read: {error}") from error


def settings_row(values: Any) -> PodcastSettings:
    where = "seed/settings.json"
    check_fields(values, PodcastSettings, where)
    podcast_settings = PodcastSettings(**values)
    check_values(podcast_settings, where)
    return podcast_settings


def feed_rows(entries: Any) -> list[Feed]:
    if not isinstance(entries, list) or not entries:
        raise CommandError("seed/feeds.json must be a list of feeds")
    feeds: list[Feed] = []
    for number, values in enumerate(entries, start=1):
        where = f"seed/feeds.json, entry {number}"
        check_fields(values, Feed, where)
        feed = Feed(**values)
        check_values(feed, where)
        feeds.append(feed)
    urls = Counter(feed.url for feed in feeds)
    if repeated := [url for url, count in urls.items() if count > 1]:
        raise CommandError(f"seed/feeds.json repeats {', '.join(repeated)}")
    return feeds


def catalog_rows(entries: Any) -> list[tuple[Area, list[Topic]]]:
    """Each area with its topics, in teaching order: positions come from the order
    in the file."""
    if not isinstance(entries, list) or not entries:
        raise CommandError("seed/catalog.json must be a list of areas")
    catalog: list[tuple[Area, list[Topic]]] = []
    for number, values in enumerate(entries, start=1):
        where = f"seed/catalog.json, area {number}"
        if not isinstance(values, dict) or set(values) != {"name", "topics"}:
            raise CommandError(f"{where} must have name and topics, and nothing else")
        name, titles = values["name"], values["topics"]
        if not isinstance(name, str):
            raise CommandError(f"{where}: name must be text")
        if not isinstance(titles, list) or not titles:
            raise CommandError(f"{where}: topics must be a list of titles")
        if not all(isinstance(title, str) for title in titles):
            raise CommandError(f"{where}: topics must be a list of titles")
        area = Area(name=name, position=number)
        check_values(area, where)
        topics: list[Topic] = []
        for position, title in enumerate(titles, start=1):
            topic = Topic(position=position, title=title, active=True)
            # The area isn't saved yet, so its link is checked when it is.
            check_values(topic, f"{where}, topic {position}", exclude=["area"])
            topics.append(topic)
        catalog.append((area, topics))
    return catalog


def check_fields(values: Any, model: type[models.Model], where: str) -> None:
    """A seed object holds every field the admin edits, each with its JSON type, and
    nothing else. Django would turn a list into its text, 12.7 minutes into 12 and
    true into 1.0, and let null through a field that may be blank."""
    if not isinstance(values, dict):
        raise CommandError(f"{where} isn't a JSON object")
    fields = [
        field
        for field in model._meta.concrete_fields
        if field.editable and not field.primary_key
    ]
    names = [field.name for field in fields]
    if missing := [name for name in names if name not in values]:
        raise CommandError(f"{where} lacks {', '.join(missing)}")
    if unknown := [name for name in values if name not in names]:
        raise CommandError(f"{where} has unknown fields: {', '.join(unknown)}")
    for field in fields:
        value = values[field.name]
        if kind := wrong_json_type(field, value):
            shown = json.dumps(value, ensure_ascii=False)[:50]
            raise CommandError(f"{where}: {field.name} must be {kind}, not {shown}")


def wrong_json_type(field: "models.Field[Any, Any]", value: Any) -> str | None:
    """The JSON type the field needs, when value doesn't have it. JSON's true and
    false are bools, never numbers. The annotation is quoted because Django's Field
    takes type arguments only in its stubs."""
    if isinstance(field, models.BooleanField):
        return None if isinstance(value, bool) else "true or false"
    if isinstance(field, models.IntegerField):
        return None if type(value) is int else "a whole number"
    if isinstance(field, models.FloatField):
        number = type(value) in (int, float) and math.isfinite(value)
        return None if number else "a number"
    return None if isinstance(value, str) else "text"


def check_values(
    row: models.Model, where: str, exclude: list[str] | None = None
) -> None:
    """Each field's checks and the model's clean(), as on a save in the admin. Not
    validate_unique: on a seeded database the file's URLs are already in the list,
    and feed_rows checks the file's own repeats."""
    try:
        row.full_clean(exclude=exclude, validate_unique=False)
    except ValidationError as error:
        problems = "; ".join(
            f"{name}: {' '.join(messages)}"
            for name, messages in error.message_dict.items()
        )
        raise CommandError(f"{where}: {problems}") from error
