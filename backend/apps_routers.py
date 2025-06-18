from typing import Any, Optional, Type

from django.conf import settings
from django.db.models import Model


class AppsRouter:
    # which labels belong in the shared auth database
    DJANGO_AUTH_APPS = {"auth", "admin", "contenttypes", "sessions"}

    def _db_for_app(self, app_label: str) -> Optional[str]:
        name = f"{app_label}_db"
        return name if name in settings.DATABASES else None

    def db_for_read(self, model: Type[Model], **hints: Any) -> Optional[str]:
        return (
            "auth_db"
            if model._meta.app_label in self.DJANGO_AUTH_APPS
            else self._db_for_app(model._meta.app_label)
        )

    def db_for_write(self, model: Type[Model], **hints: Any) -> Optional[str]:
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1: Model, obj2: Model, **hints: Any) -> Optional[bool]:
        db1 = (
            "auth_db"
            if obj1._meta.app_label in self.DJANGO_AUTH_APPS
            else self._db_for_app(obj1._meta.app_label)
        )
        db2 = (
            "auth_db"
            if obj2._meta.app_label in self.DJANGO_AUTH_APPS
            else self._db_for_app(obj2._meta.app_label)
        )
        if db1 and db1 == db2:
            return True
        return False

    def allow_migrate(
        self, db: str, app_label: str, model_name: Optional[str] = None, **hints: Any
    ) -> Optional[bool]:
        # 1) Auth apps → only on auth_db
        if app_label in self.DJANGO_AUTH_APPS:
            return db == "auth_db"

        # 2) Domain apps → only on <app_label>_db
        target = self._db_for_app(app_label)
        if target:
            return db == target

        # 3) Everything else → never migrate
        return False
