"""
Thread-local context for Lumberjack logging and spans.

This module provides context storage for logging and span tracking using contextvars,
which works across different concurrency models including:
- Standard Python threads
- Async/await
- Greenlets (gevent)
- Eventlet
"""
import contextvars
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional

from lumberjack_sdk.constants import TRACE_NAME_KEY_RESERVED_V2

if TYPE_CHECKING:
    from .spans import Span, SpanContext


class LoggingContext:
    """Context storage for Lumberjack logging and spans.

    This class stores logging context data and span context using contextvars,
    ensuring proper context isolation across different concurrency models.
    """
    _context_var: ClassVar[contextvars.ContextVar[Dict[str, Any]]
                           ] = contextvars.ContextVar('logging_context')
    _span_stack: ClassVar[contextvars.ContextVar[list["Span"]]] = \
        contextvars.ContextVar('span_stack')

    @classmethod
    def get_context(cls) -> Dict[str, Any]:
        """Get the current context dictionary.

        Returns:
            A dictionary containing context data for the current context.
        """
        try:
            return cls._context_var.get()
        except LookupError:
            return {}

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a value in the current context.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        context = cls.get_context().copy()
        context[key] = value
        cls._context_var.set(context)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get a value from the current context.

        Args:
            key: The key to retrieve
            default: Default value if key is not found

        Returns:
            The value associated with the key, or the default if not found
        """
        context = cls.get_context()
        return context.get(key, default)

    @classmethod
    def clear(cls) -> None:
        """Clear the current context."""
        cls._context_var.set({})

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all context data for the current context.

        Returns:
            A dictionary containing all context data
        """
        return cls.get_context().copy()

    @classmethod
    def update_trace_name(cls, trace_name: str) -> None:
        """Update the trace name in the current context."""
        context = cls.get_context()
        context[TRACE_NAME_KEY_RESERVED_V2] = trace_name
        cls._context_var.set(context)

    # Span context methods
    @classmethod
    def push_span(cls, span: "Span") -> None:
        """Push a span onto the current context stack.

        Args:
            span: The span to push onto the stack
        """
        # If it's an OpenTelemetry span, the context is managed automatically
        # We still maintain our stack for backward compatibility
        if hasattr(span, 'is_recording'):
            # It's an OTel span - context is handled by OTel automatically
            # Just store for backward compatibility
            try:
                current_stack = cls._span_stack.get().copy()
            except LookupError:
                current_stack = []
            current_stack.append(span)
            cls._span_stack.set(current_stack)
        else:
            # Legacy span
            try:
                current_stack = cls._span_stack.get().copy()
            except LookupError:
                current_stack = []
            current_stack.append(span)
            cls._span_stack.set(current_stack)

    @classmethod
    def pop_span(cls) -> Optional["Span"]:
        """Pop the current span from the context stack.

        Returns:
            The popped span, or None if the stack is empty
        """
        # For OpenTelemetry spans, we don't need to manage context manually
        # Just clean up our stack for backward compatibility
        try:
            current_stack = cls._span_stack.get().copy()
        except LookupError:
            return None
        if current_stack:
            span = current_stack.pop()
            cls._span_stack.set(current_stack)
            return span
        return None

    @classmethod
    def get_current_span(cls) -> Optional["Span"]:
        """Get the current active span without removing it from the stack.

        Returns:
            The current active span, or None if no span is active
        """
        # Try OpenTelemetry first
        try:
            from opentelemetry import trace
            otel_span = trace.get_current_span()
            if otel_span and otel_span.is_recording():
                return otel_span
        except ImportError:
            pass
        
        # Fallback to context var stack
        try:
            current_stack = cls._span_stack.get()
        except LookupError:
            return None
        return current_stack[-1] if current_stack else None

    @classmethod
    def get_span_context(cls) -> Optional["SpanContext"]:
        """Get the current span context.

        Returns:
            The current span context derived from the active span, or None
        """
        # Try OpenTelemetry first
        try:
            from opentelemetry import trace
            otel_span = trace.get_current_span()
            if otel_span and otel_span.is_recording():
                span_context = otel_span.get_span_context()
                if span_context.is_valid:
                    from .spans import SpanContext
                    return SpanContext(
                        trace_id=format(span_context.trace_id, "032x"),
                        span_id=format(span_context.span_id, "016x"),
                        parent_span_id=None  # OTel doesn't expose parent ID directly
                    )
        except ImportError:
            pass
        
        # Fallback to legacy span context
        current_span = cls.get_current_span()
        if current_span and hasattr(current_span, 'trace_id'):
            from .spans import SpanContext
            return SpanContext(
                trace_id=current_span.trace_id,
                span_id=current_span.span_id,
                parent_span_id=getattr(current_span, 'parent_span_id', None)
            )
        return None

    @classmethod
    def clear_span_stack(cls) -> None:
        """Clear all spans from the context stack."""
        cls._span_stack.set([])

    @classmethod
    def get_trace_id(cls) -> Optional[str]:
        """Get the current trace ID from the active span.

        Returns:
            The current trace ID, or None if no span is active
        """
        # Try OpenTelemetry first
        try:
            from opentelemetry import trace
            otel_span = trace.get_current_span()
            if otel_span and otel_span.is_recording():
                span_context = otel_span.get_span_context()
                if span_context.is_valid:
                    return format(span_context.trace_id, "032x")
        except ImportError:
            pass
        
        # Fallback to legacy spans
        current_span = cls.get_current_span()
        if current_span and hasattr(current_span, 'trace_id'):
            return current_span.trace_id
        return None
