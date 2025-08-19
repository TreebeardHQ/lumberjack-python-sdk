from .core import Lumberjack as Lumberjack
from .internal_utils.fallback_logger import sdk_logger as sdk_logger
from typing import Any

OTEL_DJANGO_AVAILABLE: bool
DJANGO_AVAILABLE: bool

class LumberjackDjango:
    @staticmethod
    def init(**kwargs: Any) -> None: ...
    @staticmethod
    def instrument(**kwargs: Any) -> None: ...
    @staticmethod
    def uninstrument() -> None: ...
