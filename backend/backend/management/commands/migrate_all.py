from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser

from backend.local_databases import require_local_databases


class Command(BaseCommand):
    help = (
        "Runs the migrations of every database: only local ones, or, with "
        "--production, the ones shown after you confirm."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--production",
            action="store_true",
            help="Shows the databases' hosts and asks before migrating them.",
        )

    def handle(self, *args: Any, production: bool, **options: Any) -> None:
        if production:
            self.confirm()
        else:
            require_local_databases()
        for alias in settings.DATABASES:
            self.stdout.write(f"Migrating {alias}")
            call_command("migrate", database=alias, verbosity=options["verbosity"])

    def confirm(self) -> None:
        self.stdout.write("The migrations will run on these databases:")
        for alias, config in settings.DATABASES.items():
            self.stdout.write(f"  {alias}: {config.get('HOST') or 'local socket'}")
        if input("Type yes to go on: ") != "yes":
            raise CommandError("Nothing was migrated.")
