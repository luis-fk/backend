from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

# An empty host, or a path, is PostgreSQL's socket on this machine.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def remote_databases(databases: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Each database outside this machine, as "alias (host)"."""
    remote = []
    for alias, config in databases.items():
        host = config.get("HOST") or ""
        if "sqlite" in config["ENGINE"] or host in LOCAL_HOSTS or host.startswith("/"):
            continue
        remote.append(f"{alias} ({host})")
    return remote


def require_local_databases() -> None:
    """Stops a command that must only touch this machine's databases: backend/.env
    may still hold the production URLs."""
    remote = remote_databases(settings.DATABASES)
    if remote:
        raise CommandError(
            f"Not local: {', '.join(remote)}. This command only runs on the local "
            "databases; check backend/.env."
        )
