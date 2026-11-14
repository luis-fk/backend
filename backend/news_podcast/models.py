from string import Formatter

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from news_podcast.api.core.config import (
    LOCAL_TZ,
    MAX_SPEECH_MINUTES,
    SHORTEST_EPISODE_MINUTES,
    SPEECH_SPEED_LIMITS,
)
from news_podcast.api.core.llm import model_name_error
from news_podcast.api.core.schemas import ModelPrice
from news_podcast.api.core.voice.providers import voice_model_error
from news_podcast.api.episode import prompts
from news_podcast.api.episode.feeds import GOOGLE_NEWS_HOST
from news_podcast.api.episode.schemas import EpisodeOptions, FeedSource

SLOWEST, FASTEST = SPEECH_SPEED_LIMITS
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


class SettingsMissing(Exception):
    """There is no settings row: only seed_news_podcast creates it."""


class PodcastSettings(models.Model):
    """The episode settings, edited in the Django admin. A single row, which only
    seed_news_podcast creates."""

    paused = models.BooleanField(
        default=False,
        help_text="The runs on Railway (the cron and Run now) end without an episode.",
    )
    min_minutes = models.PositiveSmallIntegerField(
        "minimum minutes",
        validators=[MinValueValidator(SHORTEST_EPISODE_MINUTES)],
        help_text="Length of the file on Telegram, at the speech speed.",
    )
    max_minutes = models.PositiveSmallIntegerField("maximum minutes")
    speech_speed = models.FloatField(
        validators=[MinValueValidator(SLOWEST), MaxValueValidator(FASTEST)],
        help_text="Speeds up the file itself; Telegram's speed button multiplies it.",
    )
    text_model = models.CharField(max_length=100)
    text_input_price = models.FloatField(
        "input price", validators=[MinValueValidator(0)]
    )
    text_output_price = models.FloatField(
        "output price", validators=[MinValueValidator(0)]
    )
    fallback_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Writes the text when the text model is unavailable. Optional.",
    )
    fallback_input_price = models.FloatField(
        "input price", validators=[MinValueValidator(0)]
    )
    fallback_output_price = models.FloatField(
        "output price", validators=[MinValueValidator(0)]
    )
    voice_model = models.CharField(max_length=100)
    voice_input_price = models.FloatField(
        "input price", validators=[MinValueValidator(0)]
    )
    voice_output_price = models.FloatField(
        "output price", validators=[MinValueValidator(0)]
    )
    selection_prompt = models.TextField(
        help_text=placeholders_help(prompts.SELECTION_FIELDS)
    )
    script_prompt = models.TextField(help_text=placeholders_help(prompts.SCRIPT_FIELDS))
    expand_prompt = models.TextField(
        help_text="Sent once when the script comes out short. "
        + placeholders_help(prompts.EXPAND_FIELDS)
    )
    voice_style = models.TextField(
        help_text="How the hosts talk. If the pace changes, recalibrate "
        "NATURAL_WORDS_PER_MINUTE in api/core/config.py."
    )
    headline_voice_style = models.TextField(
        help_text="How the opening headlines are read."
    )

    class Meta:
        verbose_name = "settings"
        verbose_name_plural = "settings"

    def __str__(self) -> str:
        return "Podcast settings"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        # Django runs clean() even after clean_fields() refused a value, such as a
        # null, so each check below runs only on a value of its type.
        numbers = (self.min_minutes, self.max_minutes, self.speech_speed)
        if all(isinstance(number, int | float) for number in numbers):
            speech_minutes = self.max_minutes * self.speech_speed
            if self.min_minutes > self.max_minutes:
                errors["max_minutes"] = "Must not be less than the minimum."
            elif speech_minutes > MAX_SPEECH_MINUTES:
                errors["max_minutes"] = (
                    f"{self.max_minutes} minutes at {self.speech_speed:g}x are "
                    f"{speech_minutes:g} minutes of speech, over the limit of "
                    f"{MAX_SPEECH_MINUTES} (MAX_SPEECH_MINUTES in api/core/config.py). "
                    "Lower the maximum or the speed."
                )
        for name in ("text_model", "fallback_model"):
            model = getattr(self, name)
            if isinstance(model, str) and model and (error := model_name_error(model)):
                errors[name] = error
        voice = self.voice_model
        if isinstance(voice, str) and voice and (error := voice_model_error(voice)):
            errors["voice_model"] = error
        for name, fields in PROMPT_FIELDS.items():
            prompt = getattr(self, name)
            if isinstance(prompt, str) and (error := placeholder_error(prompt, fields)):
                errors[name] = error
        if errors:
            raise ValidationError(errors)

    @classmethod
    def load(cls) -> "PodcastSettings":
        """The settings row, which only seed_news_podcast creates."""
        podcast_settings = cls.objects.order_by("pk").first()
        if podcast_settings is None:
            raise SettingsMissing(
                "Não há configurações do podcast no banco: rode seed_news_podcast "
                "(make seed no local, make seed-prod em produção)."
            )
        return podcast_settings

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
    """A news feed the episodes read, edited in the Django admin. The list comes from
    seed_news_podcast, and an empty list stays empty."""

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
        "(api/episode/config.py) are read in full.",
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
    def sources(cls) -> list[FeedSource]:
        """The active feeds, read outside the event loop, where the ORM can run."""
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
    usage = models.JSONField(default=list, help_text="Tokens of each model answer.")
    error = models.TextField(blank=True, help_text="The step that failed and why.")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.started_at.astimezone(LOCAL_TZ):%d/%m/%Y %H:%M}"
