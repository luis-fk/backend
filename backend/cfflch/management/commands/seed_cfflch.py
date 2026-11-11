from datetime import datetime
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from cfflch.api.admission_status.utils import normalize_text
from cfflch.models import AdmissionResult, ClassRoom, Users

DEMO_USERNAME = "demo"
# A known password is fine, since the seed only runs on local databases: demo is
# also the admin's login there.
DEMO_PASSWORD = "demo"
LOCAL_TIME = ZoneInfo("America/Sao_Paulo")
# An empty host, or a path, is PostgreSQL's socket on this machine.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}
CLASS_NAMES = ("Turma A", "Turma B")


class Student(NamedTuple):
    name: str
    class_name: str
    approved: bool


STUDENTS = (
    Student("Aurora Menezes Lago", "Turma A", approved=True),
    Student("Benício Prates Rocha", "Turma A", approved=False),
    Student("Celina Duarte Vaz", "Turma A", approved=True),
    Student("Davi Antunes Leal", "Turma B", approved=True),
    Student("Elisa Moraes Brito", "Turma B", approved=False),
    Student("Gael Fontes Ribeiro", "Turma B", approved=True),
)


class Command(BaseCommand):
    help = (
        "Writes cfflch's sample data to the local databases: the person demo, two "
        "classes and six students searched this year."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        require_local_databases()
        seed_demo()
        # The site opens on the browser's current year, in Brazil: a fixed year
        # would leave its list empty next year.
        year = datetime.now(LOCAL_TIME).year
        class_rooms = {name: seed_class_room(name) for name in CLASS_NAMES}
        for student in STUDENTS:
            seed_student(student, class_rooms[student.class_name], year)
        self.stdout.write(
            f"cfflch: log in as {DEMO_USERNAME}, with the password {DEMO_PASSWORD} "
            "in the admin"
        )
        self.stdout.write(f"cfflch: classes {', '.join(CLASS_NAMES)}")
        self.stdout.write(f"cfflch: {len(STUDENTS)} students searched in {year}")


def require_local_databases() -> None:
    """The seed is for this machine's databases, and backend/.env may hold the
    production URLs. The app's own copy of backend/local_databases.py, since the
    apps share no code."""
    remote: list[str] = []
    for alias, config in settings.DATABASES.items():
        host = config.get("HOST") or ""
        if "sqlite" in config["ENGINE"] or host in LOCAL_HOSTS or host.startswith("/"):
            continue
        remote.append(f"{alias} ({host})")
    if remote:
        raise CommandError(
            f"Not local: {', '.join(remote)}. The seed only writes to the local "
            "databases; check backend/.env."
        )


def seed_demo() -> None:
    """demo, active in auth and in cfflch. The site takes the name, and the admin
    the password, which every run sets again."""
    demo, _ = get_user_model().objects.get_or_create(username=DEMO_USERNAME)
    demo.set_password(DEMO_PASSWORD)
    demo.is_active = True
    demo.is_staff = True
    demo.is_superuser = True
    demo.save()
    Users.objects.update_or_create(auth_user_id=demo.pk, defaults={"active": True})


def seed_class_room(name: str) -> ClassRoom:
    class_room, _ = ClassRoom.objects.get_or_create(
        name_normalized=normalize_text(name), defaults={"name": name}
    )
    return class_room


def seed_student(student: Student, class_room: ClassRoom, year: int) -> None:
    AdmissionResult.objects.update_or_create(
        student_name_normalized=normalize_text(student.name),
        year=year,
        defaults={
            "student_name": student.name,
            "approved": student.approved,
            "class_room": class_room,
        },
    )
