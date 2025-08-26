from .core import Lumberjack as Lumberjack
from .internal_utils.fallback_logger import sdk_logger as sdk_logger
from typing import Any, Callable, Sequence

OTEL_FASTAPI_AVAILABLE: bool

class LumberjackFastAPI:
    @staticmethod
    def instrument(app: Any, server_request_hook: Callable[..., Any] | None = None, client_request_hook: Callable[..., Any] | None = None, client_response_hook: Callable[..., Any] | None = None, tracer_provider: Any | None = None, excluded_urls: Sequence[str] | None = None, meter_provider: Any | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def uninstrument() -> None: ...
