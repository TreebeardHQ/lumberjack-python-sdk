"""
OpenTelemetry-based span API for distributed tracing.

This module provides the same interface as the original span.py but uses
OpenTelemetry's tracing system internally.
"""
import traceback
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, SpanKind as OTelSpanKind

from .otel_context import OTelLoggingContext
from .spans import SpanKind, SpanStatus, SpanStatusCode  # Keep for backward compatibility
from .code_snippets import CodeSnippetExtractor


# Map Lumberjack SpanKind to OTEL SpanKind
_SPAN_KIND_MAP = {
    SpanKind.UNSPECIFIED: OTelSpanKind.INTERNAL,
    SpanKind.INTERNAL: OTelSpanKind.INTERNAL,
    SpanKind.SERVER: OTelSpanKind.SERVER,
    SpanKind.CLIENT: OTelSpanKind.CLIENT,
    SpanKind.PRODUCER: OTelSpanKind.PRODUCER,
    SpanKind.CONSUMER: OTelSpanKind.CONSUMER,
}

# Map Lumberjack status codes to OTEL status codes
_STATUS_CODE_MAP = {
    SpanStatusCode.UNSET: StatusCode.UNSET,
    SpanStatusCode.OK: StatusCode.OK,
    SpanStatusCode.ERROR: StatusCode.ERROR,
}


def start_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    span_context: Optional[Any] = None
) -> Any:
    """Start a new span using OTEL tracer.

    Args:
        name: The name of the span
        kind: The kind of span (INTERNAL, SERVER, CLIENT, etc.)
        attributes: Optional attributes to set on the span
        span_context: Optional span context for distributed tracing (OTEL context)

    Returns:
        The newly created OTEL span
    """
    # Get the tracer from the global TracerProvider
    tracer = trace.get_tracer(__name__)
    
    # Convert Lumberjack SpanKind to OTEL SpanKind
    otel_kind = _SPAN_KIND_MAP.get(kind, OTelSpanKind.INTERNAL)
    
    # Create OTEL span
    if span_context:
        # Use provided context for distributed tracing
        span = tracer.start_span(
            name,
            kind=otel_kind,
            attributes=attributes,
            context=span_context
        )
    else:
        # Use current context
        span = tracer.start_span(
            name,
            kind=otel_kind,
            attributes=attributes
        )
    
    return span


def end_span(span: Optional[Any] = None, status: Optional[SpanStatus] = None) -> None:
    """End a span.

    Args:
        span: The OTEL span to end. If None, ends the current active span.
        status: Optional status to set on the span
    """
    target_span = span or OTelLoggingContext.get_current_span()
    
    if target_span and target_span.is_recording():
        # Set status if provided
        if status:
            otel_status_code = _STATUS_CODE_MAP.get(status.code, StatusCode.UNSET)
            otel_status = Status(otel_status_code, status.message)
            target_span.set_status(otel_status)
        
        # End the span
        target_span.end()


def get_current_span() -> Optional[Any]:
    """Get the currently active OTEL span.

    Returns:
        The current active OTEL span, or None if no span is active
    """
    return OTelLoggingContext.get_current_span()


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID.

    Returns:
        The current trace ID as a hex string, or None if no span is active
    """
    return OTelLoggingContext.get_trace_id()


def set_span_attribute(key: str, value: Any, span: Optional[Any] = None) -> None:
    """Set an attribute on a span.

    Args:
        key: The attribute key
        value: The attribute value
        span: The OTEL span to set the attribute on. If None, uses current active span.
    """
    target_span = span or OTelLoggingContext.get_current_span()
    if target_span and target_span.is_recording():
        target_span.set_attribute(key, value)


def add_span_event(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    span: Optional[Any] = None
) -> None:
    """Add an event to a span.

    Args:
        name: The event name
        attributes: Optional event attributes
        span: The OTEL span to add the event to. If None, uses current active span.
    """
    target_span = span or OTelLoggingContext.get_current_span()
    if target_span and target_span.is_recording():
        target_span.add_event(name, attributes or {})


def record_exception_on_span(
    exception: Exception,
    span: Optional[Any] = None,
    escaped: bool = False,
    capture_code_snippets: bool = True,
    context_lines: int = 5
) -> None:
    """Record an exception as an event on a span with type, message and stack trace.

    Args:
        exception: The exception to record
        span: The OTEL span to record the exception on. If None, uses current active span.
        escaped: Whether the exception escaped the span
        capture_code_snippets: Whether to capture code snippets from traceback frames
        context_lines: Number of context lines to capture around error line
    """
    target_span = span or OTelLoggingContext.get_current_span()
    if not target_span or not target_span.is_recording():
        return

    # Use OTEL's built-in exception recording
    target_span.record_exception(exception, escaped=escaped)

    # Get configuration from Lumberjack singleton for code snippet capture
    from .core import Lumberjack
    lumberjack_instance = Lumberjack()

    # Use provided params or fall back to global config
    capture_enabled = (
        capture_code_snippets if capture_code_snippets is not None
        else lumberjack_instance.code_snippet_enabled
    )
    context_lines_count = (
        context_lines if context_lines is not None
        else lumberjack_instance.code_snippet_context_lines
    )

    # Capture code snippets if enabled
    if capture_enabled:
        extractor = CodeSnippetExtractor(
            context_lines=context_lines_count,
            max_frames=lumberjack_instance.code_snippet_max_frames,
            capture_locals=False,
            exclude_patterns=lumberjack_instance.code_snippet_exclude_patterns
        )
        frame_infos = extractor.extract_from_exception(exception)

        # Add code snippet information as span attributes
        if frame_infos:
            for i, frame_info in enumerate(frame_infos):
                frame_prefix = f"exception.frames.{i}"
                target_span.set_attribute(f"{frame_prefix}.filename", frame_info['filename'])
                target_span.set_attribute(f"{frame_prefix}.lineno", str(frame_info['lineno']))
                target_span.set_attribute(f"{frame_prefix}.function", frame_info['function'])

                # Add code snippet if available
                if frame_info['code_snippet']:
                    from .code_snippets import format_code_snippet
                    formatted_snippet = format_code_snippet(
                        frame_info,
                        show_line_numbers=True,
                        highlight_error=True
                    )
                    target_span.set_attribute(f"{frame_prefix}.code_snippet", formatted_snippet)

                    # Add individual context lines
                    for j, (line, line_num) in enumerate(
                        zip(frame_info['code_snippet'],
                            frame_info['context_line_numbers'])
                    ):
                        target_span.set_attribute(f"{frame_prefix}.context.{line_num}", line)

                    # Mark the error line
                    if frame_info['error_line_index'] >= 0:
                        error_line_num = frame_info['context_line_numbers'][frame_info['error_line_index']]
                        target_span.set_attribute(f"{frame_prefix}.error_lineno", str(error_line_num))

    # Set span status to ERROR
    target_span.set_status(Status(StatusCode.ERROR, str(exception)))


@contextmanager
def span_context(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
) -> Generator[Any, None, None]:
    """Context manager for creating and managing an OTEL span.

    Args:
        name: The name of the span
        kind: The kind of span
        attributes: Optional attributes to set on the span
        record_exception: Whether to record exceptions as span events

    Yields:
        The created OTEL span

    Example:
        with span_context("my_operation") as span:
            span.set_attribute("key", "value")
            # do work
    """
    # Get the tracer
    tracer = trace.get_tracer(__name__)
    otel_kind = _SPAN_KIND_MAP.get(kind, OTelSpanKind.INTERNAL)
    
    # Use OTEL's context manager for proper span lifecycle
    with tracer.start_as_current_span(
        name,
        kind=otel_kind,
        attributes=attributes
    ) as span:
        try:
            yield span
        except Exception as e:
            if record_exception:
                record_exception_on_span(e, span, escaped=True)
            else:
                span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


# Backward compatibility functions that now delegate to OTEL
class SpanWrapper:
    """Wrapper to provide backward compatibility for Lumberjack Span interface."""
    
    def __init__(self, otel_span: Any):
        self._otel_span = otel_span
        
    @property
    def trace_id(self) -> str:
        """Get trace ID as hex string."""
        return format(self._otel_span.get_span_context().trace_id, '032x')
        
    @property
    def span_id(self) -> str:
        """Get span ID as hex string."""
        return format(self._otel_span.get_span_context().span_id, '016x')
        
    @property
    def name(self) -> str:
        """Get span name."""
        return self._otel_span.name if hasattr(self._otel_span, 'name') else "unknown"
        
    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span."""
        self._otel_span.set_attribute(key, value)
        
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self._otel_span.add_event(name, attributes or {})
        
    def end(self, status: Optional[SpanStatus] = None) -> None:
        """End the span."""
        if status:
            otel_status_code = _STATUS_CODE_MAP.get(status.code, StatusCode.UNSET)
            otel_status = Status(otel_status_code, status.message)
            self._otel_span.set_status(otel_status)
        self._otel_span.end()
        
    def is_ended(self) -> bool:
        """Check if span has ended."""
        return not self._otel_span.is_recording()


def _submit_span_to_core(span: Any) -> None:
    """Submit a span to the core for batching.
    
    Note: With OTEL, spans are automatically handled by the TracerProvider
    and exported via configured exporters. This function is kept for
    backward compatibility but does nothing.
    """
    # OTEL handles span export automatically through configured exporters
    pass