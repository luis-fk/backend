import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SETTINGS = {
    "SECRET_KEY": "not-secret",
    "API_TOKEN_SECRET": "a-test-api-token-secret-with-32-characters",
    "OPEN_WEATHER_API_KEY": "none",
    "ENVIRONMENT": "development",
    "NGROK_URL": "localhost",
    "SERVER_URL": "localhost",
    "FRONT_END_URL": "http://localhost:3000",
}
DATABASE_URLS = [
    "AUTH_DATABASE_URL",
    "PLANTS_DATABASE_URL",
    "POLITICAL_CULTURE_DATABASE_URL",
    "CFFLCH_DATABASE_URL",
    "NEWS_PODCAST_DATABASE_URL",
]


def settings_read_with(env_file: Path) -> subprocess.CompletedProcess[str]:
    """Loads the settings in a new Python, where ENV_FILE is the only variable:
    the ones this test run already has would win over the file's."""
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend import settings; "
            "print(settings.DATABASES['default']['HOST'])",
        ],
        cwd=BACKEND,
        env={"ENV_FILE": str(env_file), "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
    )


def test_env_file_names_the_file_the_settings_read(tmp_path: Path) -> None:
    env_file = tmp_path / "production.env"
    lines = [f"{name}={value}" for name, value in SETTINGS.items()]
    lines += [f"{name}=postgres://u:p@db.example.com:5432/x" for name in DATABASE_URLS]
    env_file.write_text("\n".join(lines))

    result = settings_read_with(env_file)

    assert result.stdout.strip() == "db.example.com", result.stderr


def test_a_missing_env_file_stops_the_settings(tmp_path: Path) -> None:
    result = settings_read_with(tmp_path / "missing.env")

    assert result.returncode != 0
    assert "missing.env" in result.stderr
