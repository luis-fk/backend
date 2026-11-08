from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from backend.api_auth import make_user_token


class Command(BaseCommand):
    help = "Mostra um token de API do political-culture para usar no Bruno."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("user_id", type=int, help="id em political_culture.Users")
        parser.add_argument(
            "--days", type=int, default=30, help="validade em dias (padrão: 30)"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["days"] < 1:
            raise CommandError("--days precisa ser pelo menos 1.")

        lifetime = timedelta(days=options["days"])
        token = make_user_token(str(options["user_id"]), "political-culture", lifetime)
        self.stdout.write(token)
