import ast
import importlib.util
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "news_podcast"
CORE = "news_podcast.api.core"
EPISODE = "news_podcast.api.episode"
LESSON = "news_podcast.api.lesson"
MODELS = "news_podcast.models"
# The Django layer, the only code that may use the ORM, outside the event loop:
# these modules and every command.
ORM_MODULES = (MODELS, "news_podcast.admin", f"{EPISODE}.run", f"{LESSON}.run")
COMMANDS = "news_podcast.management.commands"
SEED_COMMAND = f"{COMMANDS}.seed_news_podcast"
VOICE = f"{CORE}.voice"
# The features reach the voice only through its interface, so an implementation such
# as GeminiVoice stays behind voice_provider.
VOICE_INTERFACE = (f"{VOICE}.base", f"{VOICE}.providers", f"{VOICE}.narration")


def module_name(path: Path) -> str:
    parts = path.relative_to(APP_DIR.parent).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def imports(
    source: str, module: str, is_package: bool = False
) -> list[tuple[str, str | None]]:
    """(X, Y) for each `from X import Y` and (X, None) for each `import X`, relative
    imports resolved."""
    package = module if is_package else module.rpartition(".")[0]
    found: list[tuple[str, str | None]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [(alias.name, None) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            base = importlib.util.resolve_name(name, package) if node.level else name
            found += [(base, alias.name) for alias in node.names]
    return found


def imported_modules(source: str, module: str, is_package: bool = False) -> set[str]:
    """Every module a source imports, relative imports resolved. `from X import Y`
    counts as importing X and X.Y, since Y may be a module."""
    found: set[str] = set()
    for base, name in imports(source, module, is_package):
        found.add(base)
        if name is not None:
            found.add(f"{base}.{name}")
    return found


def defined_in(base: str, name: str | None) -> str:
    """The module that defines what an import brings in: the module imported, or the
    one where the imported object was written, so a name another module re-exports
    counts where it comes from."""
    if name is None:
        return base
    try:
        if importlib.util.find_spec(f"{base}.{name}"):
            return f"{base}.{name}"
    except ModuleNotFoundError:
        pass
    value = getattr(importlib.import_module(base), name, None)
    return str(getattr(value, "__module__", None) or base)


def inside(name: str, package: str) -> bool:
    return name == package or name.startswith(f"{package}.")


def broken_rules(module: str, imports: set[str]) -> list[str]:
    forbidden: list[str] = []
    if inside(module, CORE):
        forbidden += [EPISODE, LESSON]
    if inside(module, EPISODE):
        forbidden.append(LESSON)
    if inside(module, LESSON):
        forbidden.append(EPISODE)
    if module not in ORM_MODULES and not inside(module, COMMANDS):
        forbidden.append(MODELS)
    return [
        f"{module} imports {name}"
        for name in sorted(imports)
        for package in forbidden
        if inside(name, package)
    ]


def broken_voice_rules(module: str, found: list[tuple[str, str | None]]) -> list[str]:
    if not (inside(module, EPISODE) or inside(module, LESSON)):
        return []
    broken: list[str] = []
    for base, name in found:
        target = base if name is None else f"{base}.{name}"
        if not (inside(base, VOICE) or inside(target, VOICE)):
            continue
        # A * import can bring anything, the implementations included.
        origin = VOICE if name == "*" else defined_in(base, name)
        if not any(inside(origin, allowed) for allowed in VOICE_INTERFACE):
            broken.append(f"{module} imports {target}, from {origin}")
    return broken


def test_the_app_follows_its_import_rules() -> None:
    broken: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        if "migrations" in path.relative_to(APP_DIR).parts:
            continue
        module = module_name(path)
        source = path.read_text()
        is_package = path.name == "__init__.py"
        broken += broken_rules(module, imported_modules(source, module, is_package))
        broken += broken_voice_rules(module, imports(source, module, is_package))

    assert broken == []


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("import news_podcast.models", MODELS),
        ("from news_podcast import models", MODELS),
        ("from news_podcast.models import PodcastSettings", MODELS),
        ("from news_podcast.api import episode", EPISODE),
        ("from ..episode import service", EPISODE),
        ("from ... import models", MODELS),
    ],
)
def test_core_breaks_the_rules_however_the_import_is_written(
    line: str, found: str
) -> None:
    module = f"{CORE}.example"
    imports = imported_modules(line, module)

    assert any(inside(name, found) for name in imports)
    assert broken_rules(module, imports) != []


def test_the_episode_may_use_core_but_not_the_lesson() -> None:
    module = f"{EPISODE}.service"

    assert (
        broken_rules(module, imported_modules(f"from {CORE} import config", module))
        == []
    )
    assert broken_rules(module, imported_modules("from ..lesson import run", module))
    assert broken_rules(module, imported_modules(f"import {MODELS}", module))


@pytest.mark.parametrize(
    ("module", "may_use_the_orm"),
    [
        ("news_podcast.admin", True),
        (f"{EPISODE}.run", True),
        (f"{LESSON}.run", True),
        ("news_podcast.management.commands.news_podcast", True),
        ("news_podcast.admin_actions", False),
        ("news_podcast.models_cache", False),
        (f"{EPISODE}.runner", False),
        (f"{EPISODE}.run_helpers", False),
        (f"{LESSON}.runtime", False),
    ],
)
def test_only_the_django_layer_may_import_the_models(
    module: str, may_use_the_orm: bool
) -> None:
    assert (broken_rules(module, {MODELS}) == []) is may_use_the_orm


@pytest.mark.parametrize(
    ("line", "allowed"),
    [
        ("from news_podcast.api.core.voice.narration import narrate", True),
        ("from news_podcast.api.core.voice.providers import voice_provider", True),
        ("from news_podcast.api.core.voice.providers import VOICE_PROVIDERS", True),
        ("from news_podcast.api.core.voice.base import VoiceError", True),
        ("from news_podcast.api.core.voice import narration", True),
        ("import news_podcast.api.core.voice.narration", True),
        ("from news_podcast.api.core.voice import gemini", False),
        ("from news_podcast.api.core.voice.gemini import GeminiVoice", False),
        ("from ..core.voice.gemini import GeminiVoice", False),
        ("from news_podcast.api.core.voice.providers import GeminiVoice", False),
        ("from news_podcast.api.core.voice.providers import *", False),
        ("from news_podcast.api.core import voice", False),
        ("import news_podcast.api.core.voice", False),
    ],
)
def test_the_features_reach_the_voice_only_through_its_interface(
    line: str, allowed: bool
) -> None:
    for module in (f"{EPISODE}.service", f"{LESSON}.service"):
        found = imports(line, module)

        assert (broken_voice_rules(module, found) == []) is allowed


def names_the_seed_folder(source: str) -> bool:
    """Whether a source writes a path into seed/: a string with no spaces that has
    seed as one of its parts. A sentence that mentions seed/ doesn't count."""
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and not any(char.isspace() for char in node.value)
        and "seed" in node.value.split("/")
        for node in ast.walk(ast.parse(source))
    )


def test_only_the_seed_command_reads_the_seed_folder() -> None:
    readers = [
        module_name(path)
        for path in sorted(APP_DIR.rglob("*.py"))
        if names_the_seed_folder(path.read_text())
    ]

    assert readers == [SEED_COMMAND]


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ('SEED_DIR = Path(__file__).parent / "seed"', True),
        ('path = Path("seed/settings.json")', True),
        ('path = Path("news_podcast/seed/feeds.json")', True),
        ('path = Path(f"{APP_DIR}/seed/feeds.json")', True),
        ('path = Path("./seed/feeds.json")', True),
        ('paths = APP_DIR.glob("*/seed/*.json")', True),
        ('"""Fills the database from seed/."""', False),
        ('help = "Reads the files in news_podcast/seed/."', False),
        ('logger.info("seed/settings.json was read")', False),
        ('call_command("seed_news_podcast")', False),
    ],
)
def test_the_seed_folder_rule_counts_paths_not_mentions(
    source: str, found: bool
) -> None:
    assert names_the_seed_folder(source) is found
