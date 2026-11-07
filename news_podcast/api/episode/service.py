import asyncio
import json
import logging
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, NamedTuple, TypeVar

import httpx
from pydantic import ValidationError

from news_podcast.api.episode import config
from news_podcast.api.episode.articles import build_briefs
from news_podcast.api.episode.audio import AudioError, build_voice_note
from news_podcast.api.episode.costs import (
    format_brl_rounded,
    price_for,
    total_cost_usd,
)
from news_podcast.api.episode.feeds import (
    fetch_items,
    format_for_selection,
    load_sources,
)
from news_podcast.api.episode.gemini import (
    GeminiClient,
    GeminiError,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from news_podcast.api.episode.messages import (
    MICROSOFT_LABEL,
    episode_caption,
    episode_details,
    failure_message,
    long_date,
)
from news_podcast.api.episode.microsoft_voice import (
    MicrosoftVoiceError,
    synthesize_turns,
)
from news_podcast.api.episode.options import (
    greeting,
    nearest_send,
    podcast_name,
    spoken_time,
    story_range,
    target_minutes,
    word_range,
    words_per_minute,
)
from news_podcast.api.episode.prompts import (
    EXPAND_PROMPT,
    SCRIPT_PROMPT,
    SELECTION_PROMPT,
)
from news_podcast.api.episode.schemas import (
    EpisodeOptions,
    EpisodeReport,
    GeminiPlan,
    Host,
    Narration,
    NewsItem,
    Script,
    SelectedStory,
    StoryBrief,
    StorySelection,
    Turn,
    Usage,
    VoiceOption,
)
from news_podcast.api.episode.telegram import TelegramClient, TelegramError
from news_podcast.api.episode.utils import (
    chunk_turns,
    clean_turns,
    count_words,
    format_briefs,
    news_window,
    valid_stories,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
MIN_SCRIPT_TURNS = 10


class SampleVariant(NamedTuple):
    voice: VoiceOption
    hosts: tuple[Host, Host]


SAMPLE_VARIANTS = (
    SampleVariant("microsoft", config.HOSTS),
    SampleVariant("gemini-flash-lite", config.HOSTS),
    SampleVariant("gemini-flash", config.HOSTS),
    SampleVariant("gemini-flash", config.ALTERNATIVE_HOSTS),
)


class EpisodeError(Exception):
    pass


class NewsPodcastService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        gemini: GeminiClient | None,
        telegram: TelegramClient | None,
        chat_id: str | None,
        voice: VoiceOption,
        plan: GeminiPlan,
        options: EpisodeOptions,
    ) -> None:
        self.http_client = http_client
        self.gemini = gemini
        self.telegram = telegram
        self.chat_id = chat_id
        self.voice = voice
        self.plan = plan
        self.options = options
        self.step = "início"
        self.unavailable_models: set[str] = set()
        self.voice_retry_minutes = list(config.VOICE_RETRY_MINUTES)

    async def generate_episode(self, *, scheduled: bool, send: bool) -> EpisodeReport:
        now = datetime.now(UTC)
        scheduled_for = (
            nearest_send(now, self.options.send_at, config.LOCAL_TZ)
            if scheduled
            else None
        )
        try:
            report = await self._generate(now, scheduled_for)
        except Exception as error:
            logger.exception(f"Episode failed during '{self.step}'")
            if send:
                await notify_failure(self.telegram, self.chat_id, self.step, error)
            raise

        if send:
            if scheduled_for:
                await wait_until(scheduled_for)
            await self._deliver(report)
        return report

    async def send_voice_samples(self) -> None:
        telegram, chat_id = self._require_telegram()

        with tempfile.TemporaryDirectory(prefix="news_podcast_samples_") as tmp:
            for index, variant in enumerate(SAMPLE_VARIANTS, start=1):
                workdir = Path(tmp) / f"sample_{index}"
                workdir.mkdir()
                caption = sample_caption(index, variant, self.options)
                try:
                    path, seconds = await self._sample_audio(variant, workdir)
                except (
                    GeminiError,
                    MicrosoftVoiceError,
                    AudioError,
                    EpisodeError,
                ) as error:
                    logger.warning(f"Sample {index} failed: {error}")
                    await telegram.send_message(
                        chat_id, f"{caption}\n\n❌ Falhou: {error}"
                    )
                    continue
                await telegram.send_voice(
                    chat_id,
                    path,
                    caption,
                    round(seconds),
                )

        await telegram.send_message(chat_id, SAMPLES_FOOTER)

    async def send_chat_ids(self) -> int:
        if self.telegram is None:
            raise EpisodeError("TELEGRAM_BOT_TOKEN não configurado")

        chat_ids = await self.telegram.recent_private_chat_ids()
        if not chat_ids:
            raise EpisodeError(
                "Nenhuma conversa encontrada. Mande /start para o seu bot no Telegram "
                "e rode de novo."
            )
        for chat_id in chat_ids:
            await self.telegram.send_message(
                chat_id,
                "Achei você! Salve este número como o secret TELEGRAM_CHAT_ID "
                f"no GitHub:\n<code>{chat_id}</code>",
            )
        return len(chat_ids)

    async def _generate(
        self, now: datetime, scheduled_for: datetime | None
    ) -> EpisodeReport:
        day = (scheduled_for or now).astimezone(config.LOCAL_TZ).date()
        start, end = news_window(
            now,
            scheduled_for,
            config.NEWS_WINDOW_HOURS,
            config.NEWS_CUTOFF_HOURS_BEFORE_SEND,
        )
        logger.info(
            f"Episode of {self.options.min_minutes}-{self.options.max_minutes} min "
            f"at {self.options.speech_speed:g}x, sent at {self.options.send_at:%H:%M}"
        )
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.step = "leitura dos feeds"
        sources = load_sources(config.OPML_PATH)
        items = await fetch_items(self.http_client, sources, start, end)
        logger.info(f"Collected {len(items)} items from {len(sources)} feeds")
        if not items:
            raise EpisodeError("Nenhuma notícia encontrada nos feeds")

        self.step = "seleção das notícias"
        stories, usages = await self._select_stories(items, start, end)

        self.step = "leitura das matérias"
        briefs = await build_briefs(
            self.http_client, stories, {item.id: item for item in items}
        )
        save_debug("briefs.json", [brief.model_dump() for brief in briefs])

        self.step = "roteiro"
        script, script_usages = await self._write_script(briefs, start, end, day)
        usages.extend(script_usages)
        save_debug("script.json", script.model_dump())

        with tempfile.TemporaryDirectory(prefix="news_podcast_") as tmp:
            workdir = Path(tmp)
            self.step = "voz"
            narration = await self._narrate(script.turns, workdir)
            usages.extend(narration.usages)

            self.step = "montagem do áudio"
            audio_path = config.OUTPUT_DIR / f"resumo-{day:%Y-%m-%d}.ogg"
            duration = await build_voice_note(
                narration.parts,
                audio_path,
                narration.gap_seconds,
                self.options.speech_speed,
                workdir,
            )

        caption = episode_caption(podcast_name(self.options.send_at), day)
        details = episode_details(
            day=day,
            briefs=briefs,
            usages=usages,
            plan=self.plan,
        )
        logger.info(f"Episode ready: {duration:.0f}s\n{caption}\n{details}")
        return EpisodeReport(
            audio_path=audio_path,
            duration_seconds=duration,
            caption=caption,
            details=details,
            total_usd=total_cost_usd(usages, day),
        )

    async def _select_stories(
        self, items: list[NewsItem], start: datetime, end: datetime
    ) -> tuple[list[SelectedStory], list[Usage]]:
        items_by_id = {item.id: item for item in items}
        system_prompt = selection_prompt(self.options, start, end)
        _, max_stories = story_range(self.options)

        def parse(data: Any) -> list[SelectedStory]:
            selection = StorySelection.model_validate(data)
            stories = valid_stories(selection, items_by_id, max_stories)
            if not stories:
                raise GeminiError("a seleção veio sem notícias válidas")
            return stories

        stories, usages = await self._ask_json(
            system_prompt,
            format_for_selection(items, config.LOCAL_TZ),
            "selection",
            parse,
        )
        save_debug("selection.json", [story.model_dump() for story in stories])
        log_selection(stories, items_by_id)
        return stories, usages

    async def _write_script(
        self, briefs: list[StoryBrief], start: datetime, end: datetime, day: date
    ) -> tuple[Script, list[Usage]]:
        min_words, max_words = word_range(self.options)
        system_prompt = script_prompt(self.options, day, start, end)
        user_prompt = format_briefs(briefs, words_per_minute(self.options))
        script, usages = await self._ask_json(
            system_prompt, user_prompt, "script", parse_script
        )

        words = count_words(script.turns)
        logger.info(f"Script has {words} words in {len(script.turns)} turns")
        if words >= config.SHORT_SCRIPT_RATIO * min_words:
            return script, usages

        expand_prompt = EXPAND_PROMPT.format(
            words=words,
            min_words=min_words,
            max_words=max_words,
            script=script.model_dump_json(),
        )
        try:
            longer, more_usages = await self._ask_json(
                system_prompt,
                f"{user_prompt}\n\n{expand_prompt}",
                "script",
                parse_script,
            )
        except EpisodeError as error:
            logger.warning(f"Could not lengthen the script: {error}")
            return script, usages

        usages.extend(more_usages)
        logger.info(f"Lengthened script has {count_words(longer.turns)} words")
        return (longer if count_words(longer.turns) > words else script), usages

    async def _ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        step: str,
        parse: Callable[[Any], T],
    ) -> tuple[T, list[Usage]]:
        gemini = self._require_gemini()
        usages: list[Usage] = []
        errors: list[str] = []

        for model in self._available_text_models():
            try:
                data, usage = await gemini.generate_json(
                    model, system_prompt, user_prompt, step, config.THINKING_LEVEL
                )
                usages.append(usage)
                result = parse(data)
            except GeminiUnavailableError as error:
                self.unavailable_models.add(model)
                logger.warning(
                    f"{model} is unavailable, skipping it from now on: {error}"
                )
                errors.append(f"{model}: {error}")
                continue
            except (GeminiError, ValidationError) as error:
                logger.warning(f"{model} failed during {step}: {error}")
                errors.append(f"{model}: {error}")
                continue

            return result, usages

        raise EpisodeError(" | ".join(errors) or "Nenhum modelo de texto disponível")

    def _available_text_models(self) -> list[str]:
        return [
            model
            for model in (config.TEXT_MODEL, config.TEXT_FALLBACK_MODEL)
            if model not in self.unavailable_models
        ]

    async def _narrate(self, turns: list[Turn], workdir: Path) -> Narration:
        if self.voice == "microsoft":
            return await narrate_with_microsoft(turns, workdir, [])

        model = config.TTS_MODELS[self.voice]
        usages: list[Usage] = []
        parts = await self._gemini_parts(turns, model, workdir, usages)
        return Narration(
            parts=parts,
            usages=usages,
            voice_label=config.MODEL_LABELS[model],
            gap_seconds=config.GEMINI_GAP_SECONDS,
        )

    async def _gemini_parts(
        self, turns: list[Turn], model: str, workdir: Path, usages: list[Usage]
    ) -> list[Path]:
        gemini = self._require_gemini()
        chunks = chunk_turns(turns, config.TTS_CHUNK_WORDS)
        parts: list[Path] = []
        for index, chunk in enumerate(chunks, start=1):
            logger.info(f"Gemini voice: part {index} of {len(chunks)}")
            audio, usage = await self._synthesize_patiently(gemini, model, chunk)
            usages.append(usage)
            path = workdir / f"gemini_{index:03d}.wav"
            path.write_bytes(audio)
            parts.append(path)
        return parts

    async def _synthesize_patiently(
        self, gemini: GeminiClient, model: str, turns: list[Turn]
    ) -> tuple[bytes, Usage]:
        while True:
            try:
                return await gemini.synthesize_dialogue(
                    model, turns, config.HOSTS, "voice"
                )
            except GeminiQuotaExhaustedError:
                raise
            except GeminiUnavailableError as error:
                if not self.voice_retry_minutes:
                    raise
                minutes = self.voice_retry_minutes.pop(0)
                logger.warning(
                    f"Gemini voice is unavailable ({error}); "
                    f"trying again in {minutes} min"
                )
                await asyncio.sleep(minutes * 60)

    async def _sample_audio(
        self, variant: SampleVariant, workdir: Path
    ) -> tuple[Path, float]:
        turns = [
            Turn(speaker=variant.hosts[index % 2].name, text=text)
            for index, text in enumerate(config.SAMPLE_DIALOGUE)
        ]
        if variant.voice == "microsoft":
            parts = await synthesize_turns(turns, variant.hosts, workdir)
            gap = config.MICROSOFT_GAP_SECONDS
        else:
            gemini = self._require_gemini()
            audio, _ = await gemini.synthesize_dialogue(
                config.TTS_MODELS[variant.voice], turns, variant.hosts, "voice"
            )
            part = workdir / "gemini.wav"
            part.write_bytes(audio)
            parts, gap = [part], config.GEMINI_GAP_SECONDS

        output = workdir / "amostra.ogg"
        seconds = await build_voice_note(
            parts, output, gap, self.options.speech_speed, workdir
        )
        return output, seconds

    async def _deliver(self, report: EpisodeReport) -> None:
        telegram, chat_id = self._require_telegram()
        await telegram.send_voice(
            chat_id, report.audio_path, report.caption, round(report.duration_seconds)
        )
        await telegram.send_message(chat_id, report.details)

    def _require_gemini(self) -> GeminiClient:
        if self.gemini is None:
            raise EpisodeError("GEMINI_API_KEY não configurada")
        return self.gemini

    def _require_telegram(self) -> tuple[TelegramClient, str]:
        if self.telegram is None or not self.chat_id:
            raise EpisodeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurado")
        return self.telegram, self.chat_id


async def notify_failure(
    telegram: TelegramClient | None, chat_id: str | None, step: str, error: Exception
) -> None:
    if telegram is None or not chat_id:
        return
    try:
        await telegram.send_message(chat_id, failure_message(step, error))
    except TelegramError as notify_error:
        logger.error(f"Could not report the failure on Telegram: {notify_error}")


async def narrate_with_microsoft(
    turns: list[Turn], workdir: Path, usages: list[Usage]
) -> Narration:
    parts = await synthesize_turns(turns, config.HOSTS, workdir)
    return Narration(
        parts=parts,
        usages=usages,
        voice_label=MICROSOFT_LABEL,
        gap_seconds=config.MICROSOFT_GAP_SECONDS,
    )


def parse_script(data: Any) -> Script:
    script = Script.model_validate(data)
    turns = clean_turns(script.turns, config.HOSTS)
    if len(turns) < MIN_SCRIPT_TURNS:
        raise GeminiError(f"o roteiro veio com só {len(turns)} falas")
    return script.model_copy(update={"turns": turns})


async def wait_until(moment: datetime) -> None:
    delay = (moment - datetime.now(UTC)).total_seconds()
    if 0 < delay <= config.MAX_WAIT_SECONDS:
        local_moment = moment.astimezone(config.LOCAL_TZ)
        logger.info(f"Waiting {delay / 60:.0f} min to send at {local_moment:%H:%M}")
        await asyncio.sleep(delay)


def selection_prompt(options: EpisodeOptions, start: datetime, end: datetime) -> str:
    min_stories, max_stories = story_range(options)
    return SELECTION_PROMPT.format(
        min_minutes=options.min_minutes,
        max_minutes=options.max_minutes,
        target_minutes=round(target_minutes(options)),
        min_stories=min_stories,
        max_stories=max_stories,
        window_start=local_label(start),
        window_end=local_label(end),
    )


def script_prompt(
    options: EpisodeOptions, day: date, start: datetime, end: datetime
) -> str:
    min_words, max_words = word_range(options)
    return SCRIPT_PROMPT.format(
        podcast_name=podcast_name(options.send_at),
        host_a=config.HOSTS[0].name,
        host_b=config.HOSTS[1].name,
        send_time=spoken_time(options.send_at),
        greeting=greeting(options.send_at),
        today=long_date(day),
        window_start=local_label(start),
        window_end=local_label(end),
        min_words=min_words,
        max_words=max_words,
    )


def local_label(moment: datetime) -> str:
    return moment.astimezone(config.LOCAL_TZ).strftime("%d/%m às %H:%M")


def save_debug(name: str, payload: Any) -> None:
    path = config.OUTPUT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def log_selection(
    stories: Sequence[SelectedStory], items_by_id: dict[str, NewsItem]
) -> None:
    for story in stories:
        outlets = sorted({items_by_id[item_id].outlet for item_id in story.item_ids})
        logger.info(
            f"Story ({story.minutes} min): {story.title} | {', '.join(outlets)}"
        )

    has_preferred = any(
        items_by_id[item_id].outlet in config.PREFERRED_OUTLETS
        for story in stories
        for item_id in story.item_ids
    )
    if not has_preferred:
        logger.info("No story from the preferred outlets today")


def sample_caption(index: int, variant: SampleVariant, options: EpisodeOptions) -> str:
    voices = f"{variant.hosts[0].name} e {variant.hosts[1].name}"
    header = f"🎧 <b>Amostra {index} de {len(SAMPLE_VARIANTS)}</b> · "
    if variant.voice == "microsoft":
        names = " e ".join(microsoft_voice_name(host) for host in variant.hosts)
        return (
            f"{header}{MICROSOFT_LABEL} ({voices}: {names})\n"
            "Custo da voz: grátis, sem limite.\n"
            "Configuração: NEWS_PODCAST_VOICE = microsoft"
        )

    model = config.TTS_MODELS[variant.voice]
    voice_names = f"{variant.hosts[0].gemini_voice} e {variant.hosts[1].gemini_voice}"
    today = datetime.now(config.LOCAL_TZ).date()
    return (
        f"{header}{config.MODEL_LABELS[model]} ({voices}: {voice_names})\n"
        f"Custo só da voz, episódio de {round(target_minutes(options))} min por dia: "
        f"~{monthly_voice_cost(model, today, options)}/mês agora, "
        f"~{monthly_voice_cost(model, config.PRICE_CHANGE_DAY, options)}/mês a partir "
        "de jan/27 (no plano grátis, R$ 0 enquanto durar a cota).\n"
        f"Configuração: NEWS_PODCAST_VOICE = {variant.voice}"
    )


def monthly_voice_cost(model: str, day: date, options: EpisodeOptions) -> str:
    price = price_for(model, day)
    if price is None:
        return "?"
    speech_seconds = target_minutes(options) * 60 * options.speech_speed
    tokens = speech_seconds * config.AUDIO_TOKENS_PER_SECOND * 30
    usd = tokens * price.output_per_million / 1_000_000
    return format_brl_rounded(usd * config.BRL_PER_USD)


def microsoft_voice_name(host: Host) -> str:
    return host.microsoft_voice.split("-")[-1].removesuffix("Neural")


SAMPLES_FOOTER = (
    "Pra escolher a voz, crie no GitHub a variável <b>NEWS_PODCAST_VOICE</b> "
    "(Settings → Secrets and variables → Actions → aba Variables) com "
    "<code>gemini-flash</code>, <code>gemini-flash-lite</code> ou "
    f"<code>microsoft</code>. Sem a variável, o robô usa {config.DEFAULT_VOICE}. Se "
    "a voz do Gemini falhar, ele espera e tenta de novo, sem trocar de voz."
)
