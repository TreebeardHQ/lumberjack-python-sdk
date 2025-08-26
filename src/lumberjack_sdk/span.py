"""
Span API for OpenTelemetry-compliant distributed tracing.
"""
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional, cast

from opentelemetry import trace
from opentelemetry.trace import INVALID_SPAN_CONTEXT, NonRecordingSpan, SpanContext, SpanKind, Status, StatusCode # type: ignore[attr-defined]

from .code_snippets import CodeSnippetExtractor


from .core import Lumberjack


def start_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    span_context: Optional[SpanContext] = None
) -> Optional[trace.Span]:
    """Start a new span using OpenTelemetry.

    Args:
        name: The name of the span
        kind: The kind of span (INTERNAL, SERVER, CLIENT, etc.)
        attributes: Optional attributes to set on the span
        span_context: Optional span context for distributed tracing

    Returns:
        The newly created span (OpenTelemetry span), or None if no tracer available
    """
    
    # Get tracer from Lumberjack instance
    lumberjack = Lumberjack()
    tracer = lumberjack.tracer

    if not tracer:
        return None
    
    # Create OTel context if needed
    context = None
    if span_context:
        # Use the provided span context for distributed tracing
        context = trace.set_span_in_context(trace.NonRecordingSpan(span_context))
    
    # Start the span
    span = tracer.start_span(
        name=name,
        kind=kind,
        attributes=attributes,
        context=context
    )
    
    return span


def end_span(span: Optional[trace.Span] = None, status: Optional[Status] = None) -> None:
    """End a span.

    Args:
        span: The span to end. If None, ends the current active span.
        status: Optional status to set on the span
    """
    # Determine target span
    if span is None:
        target_span = trace.get_current_span()
        if not target_span or not target_span.is_recording():
            return
    else:
        target_span = span
    
    if not target_span:
        return
    
    # Set status if provided
    if status:
        target_span.set_status(status)
    
    # End the span
    target_span.end()


def get_current_span() -> Optional[trace.Span]:
    """Get the currently active span.

    Returns:
        The current active OpenTelemetry span, or None if no span is active
    """
    otel_span = trace.get_current_span()
    if otel_span and otel_span.is_recording():
        return otel_span
    return None


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID.

    Returns:
        The current trace ID, or None if no span is active
    """
    otel_span = trace.get_current_span()
    if otel_span and otel_span.is_recording():
        span_context = otel_span.get_span_context()
        if span_context.is_valid:
            return format(span_context.trace_id, "032x")
    return None


def set_span_attribute(key: str, value: Any, span: Optional[trace.Span] = None) -> None:
    """Set an attribute on a span.

    Args:
        key: The attribute key
        value: The attribute value
        span: The span to set the attribute on. If None, uses current active span.
    """
    target_span = span or get_current_span()
    if target_span:
        target_span.set_attribute(key, value)


def add_span_event(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    span: Optional[trace.Span] = None
) -> None:
    """Add an event to a span.

    Args:
        name: The event name
        attributes: Optional event attributes
        span: The span to add the event to. If None, uses current active span.
    """
    target_span = span or get_current_span()
    if target_span:
        target_span.add_event(name, attributes)


def record_exception_on_span(
    exception: Exception,
    span: Optional[trace.Span] = None,
    escaped: bool = False,
    capture_code_snippets: bool = True,
    context_lines: int = 5
) -> None:
    """Record an exception as an event on a span with type, message and stack trace.

    Args:
        exception: The exception to record
        span: The span to record the exception on. If None, uses current active span.
        escaped: Whether the exception escaped the span
        capture_code_snippets: Whether to capture code snippets from traceback frames
        context_lines: Number of context lines to capture around error line
    """
    target_span = span or get_current_span()
    if not target_span:
        return

    # Use OpenTelemetry's built-in exception recording
    target_span.record_exception(exception, escaped=escaped)
    
    # Set span status to ERROR
    target_span.set_status(Status(StatusCode.ERROR, str(exception)))

    # Optionally add code snippets as additional attributes
    if capture_code_snippets:
        _add_code_snippets_to_span(target_span, exception, context_lines)


def _add_code_snippets_to_span(
    span: trace.Span, 
    exception: Exception, 
    context_lines: int
) -> None:
    """Add code snippets from exception traceback to span attributes."""
    lumberjack_instance = Lumberjack()

    extractor = CodeSnippetExtractor(
        context_lines=context_lines,
        max_frames=getattr(lumberjack_instance, 'code_snippet_max_frames', 10),
        capture_locals=False,
        exclude_patterns=getattr(lumberjack_instance, 'code_snippet_exclude_patterns', [])
    )
    
    try:
        frame_infos = extractor.extract_from_exception(exception)
        
        # Add frame information to attributes
        for i, frame_info in enumerate(frame_infos):
            frame_prefix = f"exception.frames.{i}"
            span.set_attribute(f"{frame_prefix}.filename", frame_info['filename'])
            span.set_attribute(f"{frame_prefix}.lineno", frame_info['lineno'])
            span.set_attribute(f"{frame_prefix}.function", frame_info['function'])

            # Add code snippet if available
            if frame_info['code_snippet']:
                from .code_snippets import format_code_snippet
                formatted_snippet = format_code_snippet(
                    frame_info,
                    show_line_numbers=True,
                    highlight_error=True
                )
                span.set_attribute(f"{frame_prefix}.code_snippet", formatted_snippet)
    except Exception:
        # If code snippet extraction fails, don't break the exception recording
        pass


@contextmanager
def span_context(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
) -> Generator[trace.Span, None, None]:
    """Context manager for creating and managing a span.

    Args:
        name: The name of the span
        kind: The kind of span
        attributes: Optional attributes to set on the span
        record_exception: Whether to record exceptions as span events

    Yields:
        The created OpenTelemetry span

    Example:
        with span_context("my_operation") as span:
            span.set_attribute("key", "value")
            # do work
    """
    
    # Get tracer from Lumberjack instance
    lumberjack = Lumberjack()
    tracer = lumberjack.tracer
    if not tracer:
        # No tracer available - yield a no-op span
        yield NonRecordingSpan(INVALID_SPAN_CONTEXT)
        return
        
    # Use OpenTelemetry's context manager
    # Cast to Any to work around pylance type issues with abstract Tracer
    with cast(Any, tracer).start_as_current_span(
        name, kind=kind, attributes=attributes
    ) as span:
        try:
            yield span
        except Exception as e:
            if record_exception:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
            raise