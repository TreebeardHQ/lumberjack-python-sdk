from functools import wraps
from typing import Any, Callable, Dict, Optional

from .span import end_span, record_exception_on_span, start_span
from opentelemetry.trace import SpanKind, Status as SpanStatus, StatusCode as SpanStatusCode # type: ignore[attr-defined]


def lumberjack_trace(name: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to clear contextvars after function completes.
    Usage:
        @lumberjack_trace
        def ...

        or with a name:
        @lumberjack_trace(name="my_trace")
        def ...

    Args:
        name: Optional name for the trace
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Use span name from decorator or function name
            span_name = name or func.__name__

            span = None

            try:
                # Start span for function execution
                span = start_span(
                    name=span_name,
                    kind=SpanKind.INTERNAL
                )

                # Set function attributes
                if span:
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    # Set argument attributes (be careful with sensitive data)
                    if args:
                        span.set_attribute("function.args_count", len(args))
                    if kwargs:
                        span.set_attribute("function.kwargs_count", len(kwargs))
                    # Only log non-sensitive kwargs
                    safe_kwargs: Dict[str, Any] = {
                        k: v for k, v in kwargs.items()
                        if not any(
                            sensitive in k.lower()
                            for sensitive in ['password', 'token', 'key', 'secret']
                        )
                    }
                    if safe_kwargs:
                        span.set_attribute("function.kwargs", str(safe_kwargs))

                # Execute function
                result = func(*args, **kwargs)

                # Set result attributes
                if result is not None and span:
                    span.set_attribute("function.result_type",
                                       type(result).__name__)
                    # Only log simple result types
                    if isinstance(result, (str, int, float, bool)):
                        span.set_attribute("function.result", str(result))

                # Complete span with success
                end_span(span, SpanStatus(SpanStatusCode.OK))

                return result

            except Exception as e:
                # End span with error status
                if span:
                    # Record exception with full traceback
                    record_exception_on_span(e, span)
                    end_span(span)

                raise  # re-raises the same exception, with full traceback

        return wrapper

    return decorator
