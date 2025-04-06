from typing import Any, Optional, Type

from django.db.models import Model


class AppsRouter:
    def db_for_read(self, model: Type[Model], **hints: Any) -> Optional[str]:
        if getattr(model._meta, "app_label", None) == "plants":
            return "plants_db"
        elif getattr(model._meta, "app_label", None) == "political_culture":
            return "political_culture_db"
        return None

    def db_for_write(self, model: Type[Model], **hints: Any) -> Optional[str]:
        if getattr(model._meta, "app_label", None) == "plants":
            return "plants_db"
        elif getattr(model._meta, "app_label", None) == "political_culture":
            return "political_culture_db"
        return None

    def allow_relation(self, obj1: Model, obj2: Model, **hints: Any) -> Optional[bool]:
        if (
            getattr(obj1._meta, "app_label", None) == "plants"
            and getattr(obj2._meta, "app_label", None) == "plants"
        ):
            return True
        elif (
            getattr(obj1._meta, "app_label", None) == "political_culture"
            and getattr(obj2._meta, "app_label", None) == "political_culture"
        ):
            return True
        return None

    def allow_migrate(
        self, db: str, app_label: str, model_name: Optional[str] = None, **hints: Any
    ) -> Optional[bool]:
        if app_label == "plants":
            return db == "plants_db"
        elif app_label == "political_culture":
            return db == "political_culture_db"
        return None
