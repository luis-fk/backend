from functools import partial
from string import Formatter
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from news_podcast.api.episode import config, prompts
from news_podcast.api.episode.feeds import GOOGLE_NEWS_HOST
from news_podcast.api.episode.schemas import EpisodeOptions, FeedSource, ModelPrice

SLOWEST, FASTEST = config.SPEECH_SPEED_LIMITS
BRACES_HELP = "Write a literal brace as {{ or }}."
PROMPT_FIELDS = {
    "selection_prompt": prompts.SELECTION_FIELDS,
    "script_prompt": prompts.SCRIPT_FIELDS,
    "expand_prompt": prompts.EXPAND_FIELDS,
}


def placeholders_help(fields: tuple[str, ...]) -> str:
    names = ", ".join(f"{{{field}}}" for field in fields)
    return f"Placeholders, with no format: {names}. {BRACES_HELP}"


def placeholder_error(template: str, fields: tuple[str, ...]) -> str | None:
    """What would break when the service fills in the template, if anything. Only
    plain placeholders are safe: the values come as text or numbers, so a format
    like {today:%d} breaks too."""
    try:
        parts = list(Formatter().parse(template))
    except ValueError as error:
        return f"{error}. {BRACES_HELP}"
    for _, name, format_spec, conversion in parts:
        if name is None:
            continue
        if name not in fields:
            return f"Unknown placeholder {{{name}}}. {placeholders_help(fields)}"
        if format_spec or conversion:
            return f"Write {{{name}}} without a format (: or !)."
    return None


# The values a new settings row starts with. The fields read them through
# starting_value, so a migration records only the field's name, and editing a
# value in config.py or prompts.py needs no migration.
STARTING_VALUES: dict[str, Any] = {
    "min_minutes": config.DEFAULT_MIN_MINUTES,
    "max_minutes": config.DEFAULT_MAX_MINUTES,
    "speech_speed": config.DEFAULT_SPEECH_SPEED,
    "text_model": config.TEXT_MODEL,
    "text_input_price": config.TEXT_MODEL_PRICE.input_per_million,
    "text_output_price": config.TEXT_MODEL_PRICE.output_per_million,
    "fallback_model": config.TEXT_FALLBACK_MODEL,
    "fallback_input_price": config.TEXT_FALLBACK_MODEL_PRICE.input_per_million,
    "fallback_output_price": config.TEXT_FALLBACK_MODEL_PRICE.output_per_million,
    "voice_model": config.TTS_MODEL,
    "voice_input_price": config.TTS_MODEL_PRICE.input_per_million,
    "voice_output_price": config.TTS_MODEL_PRICE.output_per_million,
    "selection_prompt": prompts.SELECTION_PROMPT,
    "script_prompt": prompts.SCRIPT_PROMPT,
    "expand_prompt": prompts.EXPAND_PROMPT,
    "voice_style": config.TTS_STYLE,
    "headline_voice_style": config.HEADLINE_TTS_STYLE,
}


def starting_value(field_name: str) -> Any:
    return STARTING_VALUES[field_name]


class PodcastSettings(models.Model):
    """The episode settings, edited in the Django admin. A single row, which starts
    with the values in config.py and prompts.py."""

    paused = models.BooleanField(
        default=False,
        help_text="The runs on Railway (the cron and Run now) end without an episode.",
    )
    min_minutes = models.PositiveSmallIntegerField(
        "minimum minutes",
        default=partial(starting_value, "min_minutes"),
        validators=[MinValueValidator(config.SHORTEST_EPISODE_MINUTES)],
        help_text="Length of the file on Telegram, at the speech speed.",
    )
    max_minutes = models.PositiveSmallIntegerField(
        "maximum minutes", default=partial(starting_value, "max_minutes")
    )
    speech_speed = models.FloatField(
        default=partial(starting_value, "speech_speed"),
        validators=[MinValueValidator(SLOWEST), MaxValueValidator(FASTEST)],
        help_text="Speeds up the file itself; Telegram's speed button multiplies it.",
    )
    text_model = models.CharField(
        max_length=100, default=partial(starting_value, "text_model")
    )
    text_input_price = models.FloatField(
        "input price",
        default=partial(starting_value, "text_input_price"),
        validators=[MinValueValidator(0)],
    )
    text_output_price = models.FloatField(
        "output price",
        default=partial(starting_value, "text_output_price"),
        validators=[MinValueValidator(0)],
    )
    fallback_model = models.CharField(
        max_length=100,
        blank=True,
        default=partial(starting_value, "fallback_model"),
        help_text="Writes the text when the text model is unavailable. Optional.",
    )
    fallback_input_price = models.FloatField(
        "input price",
        default=partial(starting_value, "fallback_input_price"),
        validators=[MinValueValidator(0)],
    )
    fallback_output_price = models.FloatField(
        "output price",
        default=partial(starting_value, "fallback_output_price"),
        validators=[MinValueValidator(0)],
    )
    voice_model = models.CharField(
        max_length=100, default=partial(starting_value, "voice_model")
    )
    voice_input_price = models.FloatField(
        "input price",
        default=partial(starting_value, "voice_input_price"),
        validators=[MinValueValidator(0)],
    )
    voice_output_price = models.FloatField(
        "output price",
        default=partial(starting_value, "voice_output_price"),
        validators=[MinValueValidator(0)],
    )
    selection_prompt = models.TextField(
        default=partial(starting_value, "selection_prompt"),
        help_text=placeholders_help(prompts.SELECTION_FIELDS),
    )
    script_prompt = models.TextField(
        default=partial(starting_value, "script_prompt"),
        help_text=placeholders_help(prompts.SCRIPT_FIELDS),
    )
    expand_prompt = models.TextField(
        default=partial(starting_value, "expand_prompt"),
        help_text="Sent once when the script comes out short. "
        + placeholders_help(prompts.EXPAND_FIELDS),
    )
    voice_style = models.TextField(
        default=partial(starting_value, "voice_style"),
        help_text="How the hosts talk. If the pace changes, recalibrate "
        "NATURAL_WORDS_PER_MINUTE in config.py.",
    )
    headline_voice_style = models.TextField(
        default=partial(starting_value, "headline_voice_style"),
        help_text="How the opening headlines are read.",
    )

    class Meta:
        verbose_name = "settings"
        verbose_name_plural = "settings"

    def __str__(self) -> str:
        return "Podcast settings"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        speech_minutes = self.max_minutes * self.speech_speed
        if self.min_minutes > self.max_minutes:
            errors["max_minutes"] = "Must not be less than the minimum."
        elif speech_minutes > config.MAX_SPEECH_MINUTES:
            errors["max_minutes"] = (
                f"{self.max_minutes} minutes at {self.speech_speed:g}x are "
                f"{speech_minutes:g} minutes of speech, over the limit of "
                f"{config.MAX_SPEECH_MINUTES} (MAX_SPEECH_MINUTES in config.py). Lower "
                "the maximum or the speed."
            )
        for name, fields in PROMPT_FIELDS.items():
            error = placeholder_error(getattr(self, name), fields)
            if error:
                errors[name] = error
        if errors:
            raise ValidationError(errors)

    @classmethod
    def load(cls) -> "PodcastSettings":
        """The settings row, created with the starting values the first time a run
        or the admin needs it."""
        return cls.objects.order_by("pk").first() or cls.objects.create()

    def episode_options(self) -> EpisodeOptions:
        return EpisodeOptions(self.min_minutes, self.max_minutes, self.speech_speed)

    def text_models(self) -> list[str]:
        return [model for model in (self.text_model, self.fallback_model) if model]

    def prices(self) -> dict[str, ModelPrice]:
        rows = [
            (self.text_model, self.text_input_price, self.text_output_price),
            (
                self.fallback_model,
                self.fallback_input_price,
                self.fallback_output_price,
            ),
            (self.voice_model, self.voice_input_price, self.voice_output_price),
        ]
        return {
            model: ModelPrice(input_price, output_price)
            for model, input_price, output_price in rows
            if model
        }


class Feed(models.Model):
    """A news feed the episodes read, edited in the Django admin. The list starts with
    STARTING_FEEDS in config.py the first time a run or the admin needs it."""

    class Section(models.TextChoices):
        ECONOMIA = "Economia"
        GERAL = "Geral"
        MUNDO = "Mundo"
        POLITICA = "Política"

    outlet = models.CharField(
        max_length=100,
        help_text="Give an outlet's feeds the same name: a story reads one source per "
        "outlet, and a headline in two of its feeds counts once.",
    )
    section = models.CharField(max_length=20, choices=Section.choices)
    url = models.URLField(
        "URL",
        max_length=500,
        unique=True,
        help_text="An RSS feed, or a Google News search like "
        "https://news.google.com/rss/search?q=site:site.com.br+when:1d"
        "&hl=pt-BR&gl=BR&ceid=BR:pt-419. Only the sites in FULL_TEXT_DOMAINS "
        "(config.py) are read in full.",
    )
    active = models.BooleanField(
        default=True, help_text="Turned off, the episodes don't read it."
    )

    class Meta:
        # Of a headline in two feeds of one outlet, the first feed's copy stays.
        ordering = ["section", "pk"]

    def __str__(self) -> str:
        return f"{self.outlet} · {self.section}"

    @classmethod
    def start_if_empty(cls) -> None:
        if not Feed.objects.exists():
            Feed.objects.bulk_create(
                Feed(outlet=outlet, section=section, url=url)
                for outlet, section, url in config.STARTING_FEEDS
            )

    @classmethod
    def sources(cls) -> list[FeedSource]:
        """The active feeds, read outside the event loop, where the ORM can run."""
        cls.start_if_empty()
        return [feed.source() for feed in cls.objects.filter(active=True)]

    def source(self) -> FeedSource:
        return FeedSource(
            outlet=self.outlet,
            section=self.section,
            url=self.url,
            via_google_news=GOOGLE_NEWS_HOST in self.url,
        )


class Episode(models.Model):
    """One run of the podcast, kept for its cost and its outcome. The audio is not
    kept."""

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        NOT_SENT = "not_sent", "Not sent (--no-send)"
        FAILED = "failed", "Failed"

    started_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices)
    duration_seconds = models.FloatField(null=True, blank=True)
    script_words = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Words in the script; with the length, they give the voice's pace.",
    )
    cost_usd = models.FloatField(
        "cost (US$)", help_text="Paid-plan cost, at the prices in the settings."
    )
    usage = models.JSONField(default=list, help_text="Tokens of each Gemini answer.")
    error = models.TextField(blank=True, help_text="The step that failed and why.")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.started_at.astimezone(config.LOCAL_TZ):%d/%m/%Y %H:%M}"
