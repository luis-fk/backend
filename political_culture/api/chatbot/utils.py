import re
from typing import Any, Callable, Dict, Type, TypeVar

T = TypeVar("T")


def singleton(cls: Type[T]) -> Callable[..., T]:
    instances: Dict[Type[T], T] = {}

    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


def clean_html(html_string: str) -> str:
    return re.sub(r"<[^>]+>", "", html_string)
