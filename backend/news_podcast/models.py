from string import Formatter

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from news_podcast.api.episode import config, prompts
from news_podcast.api.episode.schemas import EpisodeOptions, ModelPrice

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


class PodcastSettings(models.Model):
    """The episode settings, edited in the Django admin. A single row, which starts
    with the values in config.py and prompts.py."""

    paused = models.BooleanField(
        default=False,
        help_text="The runs on Railway (the cron and Run now) end without an episode.",
    )
    min_minutes = models.PositiveSmallIntegerField(
        "minimum minutes",
        default=config.DEFAULT_MIN_MINUTES,
        validators=[MinValueValidator(config.SHORTEST_EPISODE_MINUTES)],
        help_text="Length of the file on Telegram, at the speech speed.",
    )
    max_minutes = models.PositiveSmallIntegerField(
        "maximum minutes", default=config.DEFAULT_MAX_MINUTES
    )
    speech_speed = models.FloatField(
        default=config.DEFAULT_SPEECH_SPEED,
        validators=[MinValueValidator(SLOWEST), MaxValueValidator(FASTEST)],
        help_text="Speeds up the file itself; Telegram's speed button multiplies it.",
    )
    text_model = models.CharField(max_length=100, default=config.TEXT_MODEL)
    text_input_price = models.FloatField(
        "input price",
        default=config.TEXT_MODEL_PRICE.input_per_million,
        validators=[MinValueValidator(0)],
    )
    text_output_price = models.FloatField(
        "output price",
        default=config.TEXT_MODEL_PRICE.output_per_million,
        validators=[MinValueValidator(0)],
    )
    fallback_model = models.CharField(
        max_length=100,
        blank=True,
        default=config.TEXT_FALLBACK_MODEL,
        help_text="Writes the text when the text model is unavailable. Optional.",
    )
    fallback_input_price = models.FloatField(
        "input price",
        default=config.TEXT_FALLBACK_MODEL_PRICE.input_per_million,
        validators=[MinValueValidator(0)],
    )
    fallback_output_price = models.FloatField(
        "output price",
        default=config.TEXT_FALLBACK_MODEL_PRICE.output_per_million,
        validators=[MinValueValidator(0)],
    )
    voice_model = models.CharField(max_length=100, default=config.TTS_MODEL)
    voice_input_price = models.FloatField(
        "input price",
        default=config.TTS_MODEL_PRICE.input_per_million,
        validators=[MinValueValidator(0)],
    )
    voice_output_price = models.FloatField(
        "output price",
        default=config.TTS_MODEL_PRICE.output_per_million,
        validators=[MinValueValidator(0)],
    )
    selection_prompt = models.TextField(
        default=prompts.SELECTION_PROMPT,
        help_text=placeholders_help(prompts.SELECTION_FIELDS),
    )
    script_prompt = models.TextField(
        default=prompts.SCRIPT_PROMPT,
        help_text=placeholders_help(prompts.SCRIPT_FIELDS),
    )
    expand_prompt = models.TextField(
        default=prompts.EXPAND_PROMPT,
        help_text="Sent once when the script comes out short. "
        + placeholders_help(prompts.EXPAND_FIELDS),
    )
    voice_style = models.TextField(
        default=config.TTS_STYLE,
        help_text="How the hosts talk. If the pace changes, recalibrate "
        "NATURAL_WORDS_PER_MINUTE in config.py.",
    )
    headline_voice_style = models.TextField(
        default=config.HEADLINE_TTS_STYLE,
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
