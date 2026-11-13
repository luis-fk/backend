import ast
import importlib.util
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "news_podcast"
CORE = "news_podcast.api.core"
EPISODE = "news_podcast.api.episode"
LESSON = "news_podcast.api.lesson"
MODELS = "news_podcast.models"
# The Django layer: the only modules that may use the ORM, outside the event loop.
ORM_MODULES = (
    "news_podcast.models",
    "news_podcast.admin",
    f"{EPISODE}.run",
    f"{LESSON}.run",
    "news_podcast.management.commands.",
)


def module_name(path: Path) -> str:
    parts = path.relative_to(APP_DIR.parent).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def imported_modules(source: str, module: str, is_package: bool = False) -> set[str]:
    """Every module a source imports, relative imports resolved. `from X import Y`
    counts as importing X and X.Y, since Y may be a module."""
    package = module if is_package else module.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            base = importlib.util.resolve_name(name, package) if node.level else name
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


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
    if not module.startswith(ORM_MODULES) and module != MODELS:
        forbidden.append(MODELS)
    return [
        f"{module} imports {name}"
        for name in sorted(imports)
        for package in forbidden
        if inside(name, package)
    ]


def test_the_app_follows_its_import_rules() -> None:
    broken: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        if "migrations" in path.relative_to(APP_DIR).parts:
            continue
        module = module_name(path)
        imports = imported_modules(
            path.read_text(), module, is_package=path.name == "__init__.py"
        )
        broken += broken_rules(module, imports)

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
    assert broken_rules(f"{EPISODE}.run", {MODELS}) == []
