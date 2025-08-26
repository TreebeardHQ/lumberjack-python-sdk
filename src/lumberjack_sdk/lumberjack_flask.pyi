from .core import Lumberjack as Lumberjack
from .internal_utils.fallback_logger import sdk_logger as sdk_logger
from typing import Any, Callable, Sequence

OTEL_FLASK_AVAILABLE: bool

class LumberjackFlask:
    @staticmethod
    def instrument(app: Any, request_hook: Callable[..., Any] | None = None, response_hook: Callable[..., Any] | None = None, tracer_provider: Any | None = None, excluded_urls: Sequence[str] | None = None, enable_commenter: bool = True, commenter_options: dict[str, Any] | None = None, meter_provider: Any | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def uninstrument() -> None: ...
