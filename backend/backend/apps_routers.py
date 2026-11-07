from typing import Any, Type

from django.conf import settings
from django.db.models import Model


class AppsRouter:
    DJANGO_AUTH_APPS = {"auth", "admin", "contenttypes", "sessions"}

    def _db_for_app(self, app_label: str) -> str | None:
        name = f"{app_label}_db"
        return name if name in settings.DATABASES else None

    def db_for_read(self, model: Type[Model], **hints: Any) -> str | None:
        return (
            "default"
            if model._meta.app_label in self.DJANGO_AUTH_APPS
            else self._db_for_app(model._meta.app_label)
        )

    def db_for_write(self, model: Type[Model], **hints: Any) -> str | None:
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1: Model, obj2: Model, **_hints: Any) -> bool | None:
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)
        if db1 and db1 == db2:
            return True
        return None

    def allow_migrate(
        self, db: str, app_label: str, model_name: str | None = None, **hints: Any
    ) -> bool | None:
        if app_label in self.DJANGO_AUTH_APPS:
            return db == "default"

        target = self._db_for_app(app_label)
        if target:
            return db == target

        return None
