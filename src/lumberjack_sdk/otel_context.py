"""
OpenTelemetry-based context management for Lumberjack logging and spans.

This module provides context storage using OpenTelemetry's context system,
which provides robust context propagation across different concurrency models.
"""
from typing import Any, Dict, Optional

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.context import Context

from lumberjack_sdk.constants import TRACE_NAME_KEY_RESERVED_V2


# Context key for storing custom Lumberjack context data
_LUMBERJACK_CONTEXT_KEY = otel_context.create_key("lumberjack_context")


class OTelLoggingContext:
    """OTEL-based context storage for Lumberjack logging and spans.

    This class provides the same interface as LoggingContext but uses
    OpenTelemetry's context system for robust context propagation.
    """

    @classmethod
    def get_context(cls) -> Dict[str, Any]:
        """Get the current Lumberjack context dictionary.

        Returns:
            A dictionary containing context data for the current context.
        """
        current_context = otel_context.get_current()
        lumberjack_data = current_context.get(_LUMBERJACK_CONTEXT_KEY)
        return lumberjack_data.copy() if lumberjack_data else {}

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a value in the current context.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        current_context = otel_context.get_current()
        lumberjack_data = current_context.get(_LUMBERJACK_CONTEXT_KEY, {}).copy()
        lumberjack_data[key] = value
        
        # Create new context with updated data
        new_context = otel_context.set_value(_LUMBERJACK_CONTEXT_KEY, lumberjack_data, current_context)
        otel_context.attach(new_context)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get a value from the current context.

        Args:
            key: The key to retrieve
            default: Default value if key is not found

        Returns:
            The value associated with the key, or the default if not found
        """
        context_data = cls.get_context()
        return context_data.get(key, default)

    @classmethod
    def clear(cls) -> None:
        """Clear the current Lumberjack context."""
        current_context = otel_context.get_current()
        new_context = otel_context.set_value(_LUMBERJACK_CONTEXT_KEY, {}, current_context)
        otel_context.attach(new_context)

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all context data for the current context.

        Returns:
            A dictionary containing all context data
        """
        return cls.get_context()

    @classmethod
    def update_trace_name(cls, trace_name: str) -> None:
        """Update the trace name in the current context."""
        cls.set(TRACE_NAME_KEY_RESERVED_V2, trace_name)

    # Span context methods - these now delegate to OTEL's span context
    @classmethod
    def push_span(cls, span: Any) -> None:
        """Push a span onto the current context stack.
        
        Note: With OTEL, this is handled automatically by the tracer
        when using start_as_current_span() or similar methods.
        This method is kept for backward compatibility.

        Args:
            span: The span to push onto the stack (ignored in OTEL implementation)
        """
        # In OTEL, span context is managed automatically
        # This method is kept for backward compatibility
        pass

    @classmethod
    def pop_span(cls) -> Optional[Any]:
        """Pop the current span from the context stack.
        
        Note: With OTEL, this is handled automatically when spans end.
        This method is kept for backward compatibility.

        Returns:
            None (OTEL manages span lifecycle automatically)
        """
        # In OTEL, span context is managed automatically
        # This method is kept for backward compatibility
        return None

    @classmethod
    def get_current_span(cls) -> Optional[Any]:
        """Get the current active span.

        Returns:
            The current active OTEL span, or None if no span is active
        """
        return trace.get_current_span()

    @classmethod
    def get_span_context(cls) -> Optional[Any]:
        """Get the current span context.

        Returns:
            The current OTEL span context, or None if no span is active
        """
        current_span = cls.get_current_span()
        if current_span and current_span.is_recording():
            return current_span.get_span_context()
        return None

    @classmethod
    def clear_span_stack(cls) -> None:
        """Clear all spans from the context stack.
        
        Note: With OTEL, span lifecycle is managed automatically.
        This method is kept for backward compatibility.
        """
        # In OTEL, span context is managed automatically
        # This method is kept for backward compatibility
        pass

    @classmethod
    def get_trace_id(cls) -> Optional[str]:
        """Get the current trace ID from the active span.

        Returns:
            The current trace ID as a hex string, or None if no span is active
        """
        span_context = cls.get_span_context()
        if span_context and span_context.trace_id:
            return format(span_context.trace_id, '032x')
        return None

    @classmethod
    def get_span_id(cls) -> Optional[str]:
        """Get the current span ID from the active span.

        Returns:
            The current span ID as a hex string, or None if no span is active
        """
        span_context = cls.get_span_context()
        if span_context and span_context.span_id:
            return format(span_context.span_id, '016x')
        return None

    @classmethod
    def attach_context(cls, context: Context) -> Any:
        """Attach an OTEL context.
        
        Args:
            context: The OTEL context to attach
            
        Returns:
            A token that can be used to detach the context
        """
        return otel_context.attach(context)

    @classmethod
    def detach_context(cls, token: Any) -> None:
        """Detach an OTEL context.
        
        Args:
            token: The token returned by attach_context
        """
        otel_context.detach(token)

    @classmethod
    def get_current_otel_context(cls) -> Context:
        """Get the current OTEL context.
        
        Returns:
            The current OTEL context
        """
        return otel_context.get_current()