from .span import end_span as end_span, record_exception_on_span as record_exception_on_span, start_span as start_span
from typing import Any, Callable

def lumberjack_trace(name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
