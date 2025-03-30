from typing import Any, Optional, Type
from django.db.models import Model

class AuthRouter:
    def db_for_read(self, model: Type[Model], **hints: Any) -> Optional[str]:
        if model._meta.app_label in {"auth", "admin", "contenttypes", "sessions"}:
            return "auth_db"
        return None

    def db_for_write(self, model: Type[Model], **hints: Any) -> Optional[str]:
        if model._meta.app_label in {"auth", "admin", "contenttypes", "sessions"}:
            return "auth_db"
        return None

    def allow_relation(self, obj1: Model, obj2: Model, **hints: Any) -> Optional[bool]:
        # Allow relations if both objects are in the auth-related apps.
        if (
            obj1._meta.app_label in {"auth", "admin", "contenttypes", "sessions"}
            and obj2._meta.app_label in {"auth", "admin", "contenttypes", "sessions"}
        ):
            return True
        return None

    def allow_migrate(
        self, db: str, app_label: str, model_name: Optional[str] = None, **hints: Any
    ) -> Optional[bool]:
        if app_label in {"auth", "admin", "contenttypes", "sessions"}:
            return db == "auth_db"
        return None
