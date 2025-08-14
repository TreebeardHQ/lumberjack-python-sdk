"""
Trace utility functions for Lumberjack SDK.

This module provides helper functions for working with distributed tracing
using OpenTelemetry's built-in W3C trace context propagation.
"""
from typing import Dict, Optional, Union

from opentelemetry import context, trace
from opentelemetry.trace import SpanContext
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


def extract_trace_context(
    headers: Union[Dict[str, str], str], 
    carrier_key: str = 'traceparent'
) -> Optional[context.Context]:
    """Extract OpenTelemetry context from W3C trace context headers.

    Uses OpenTelemetry's built-in W3C trace context propagation to properly
    extract and validate trace context from incoming headers.

    Args:
        headers: Either a dict of headers or a single traceparent header string
        carrier_key: The header key name (default: 'traceparent')

    Returns:
        OpenTelemetry Context with trace information, or None if invalid

    Example:
        >>> # From headers dict
        >>> headers = {'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'}
        >>> ctx = extract_trace_context(headers)
        
        >>> # From single header string
        >>> header = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        >>> ctx = extract_trace_context(header)
    """
    propagator = TraceContextTextMapPropagator()
    
    # Handle both dict and string inputs
    if isinstance(headers, str):
        carrier = {carrier_key: headers}
    else:
        carrier = headers
    
    try:
        extracted_context = propagator.extract(carrier)
        
        # Verify that we actually extracted valid trace context
        span = trace.get_current_span(extracted_context)
        span_context = span.get_span_context()
        
        if span_context.is_valid:
            return extracted_context
        else:
            return None
            
    except Exception:
        return None


def get_span_context_from_headers(
    headers: Union[Dict[str, str], str], 
    carrier_key: str = 'traceparent'
) -> Optional[SpanContext]:
    """Get SpanContext from W3C trace context headers.

    Args:
        headers: Either a dict of headers or a single traceparent header string
        carrier_key: The header key name (default: 'traceparent')

    Returns:
        OpenTelemetry SpanContext if parsing succeeds, None otherwise

    Example:
        >>> headers = {'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'}
        >>> span_context = get_span_context_from_headers(headers)
        >>> if span_context:
        ...     print(f"Trace ID: {format(span_context.trace_id, '032x')}")
        ...     print(f"Span ID: {format(span_context.span_id, '016x')}")
    """
    extracted_context = extract_trace_context(headers, carrier_key)
    if not extracted_context:
        return None
    
    span = trace.get_current_span(extracted_context)
    return span.get_span_context()


def start_span_with_remote_parent(
    span_name: str,
    headers: Union[Dict[str, str], str],
    tracer: Optional[trace.Tracer] = None,
    carrier_key: str = 'traceparent'
) -> trace.Span:
    """Start a new span as a child of a remote parent from headers.

    This is a convenience function that extracts trace context from headers
    and starts a new span as a child of the remote parent.

    Args:
        span_name: Name for the new span
        headers: Either a dict of headers or a single traceparent header string
        tracer: Optional tracer instance (uses default if not provided)
        carrier_key: The header key name (default: 'traceparent')

    Returns:
        New span that is a child of the remote parent

    Example:
        >>> headers = {'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'}
        >>> with start_span_with_remote_parent("my-operation", headers) as span:
        ...     span.set_attribute("operation.type", "processing")
        ...     # Your code here
    """
    if tracer is None:
        tracer = trace.get_tracer(__name__)
    
    extracted_context = extract_trace_context(headers, carrier_key)
    
    if extracted_context:
        # Start span with the extracted context as parent
        return tracer.start_span(span_name, context=extracted_context)
    else:
        # No valid parent context, start a new root span
        return tracer.start_span(span_name)


def inject_trace_context(
    context_to_inject: Optional[context.Context] = None,
    carrier: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Inject current trace context into headers for outgoing requests.

    Uses OpenTelemetry's built-in W3C trace context propagation to inject
    the current trace context into headers.

    Args:
        context_to_inject: Optional context to inject (uses current if not provided)
        carrier: Optional carrier dict to inject into (creates new if not provided)

    Returns:
        Dictionary with trace context headers

    Example:
        >>> # Inject current context
        >>> headers = inject_trace_context()
        >>> print(headers)  # {'traceparent': '00-...', 'tracestate': '...'}
        
        >>> # Inject into existing headers
        >>> existing_headers = {'content-type': 'application/json'}
        >>> headers = inject_trace_context(carrier=existing_headers)
    """
    propagator = TraceContextTextMapPropagator()
    
    if carrier is None:
        carrier = {}
    
    if context_to_inject is None:
        context_to_inject = context.get_current()
    
    propagator.inject(carrier, context_to_inject)
    return carrier


# Legacy compatibility functions (using OpenTelemetry under the hood)
def parse_traceparent(traceparent: str) -> Optional[Dict[str, str]]:
    """Parse W3C traceparent header into its components.
    
    Note: This is a legacy function. Consider using get_span_context_from_headers()
    or extract_trace_context() for better OpenTelemetry integration.

    Args:
        traceparent: The traceparent header value

    Returns:
        Dictionary with 'trace_id', 'parent_id', and 'flags', or None if invalid
    """
    span_context = get_span_context_from_headers(traceparent)
    if not span_context:
        return None
    
    # Parse the original header to get version and flags
    parts = traceparent.strip().split('-')
    if len(parts) != 4:
        return None
    
    return {
        'version': parts[0],
        'trace_id': format(span_context.trace_id, '032x'),
        'parent_id': format(span_context.span_id, '016x'),
        'flags': parts[3]
    }


def establish_trace_context(
    trace_id: str,
    parent_span_id: str,
    clear_existing: bool = True
) -> SpanContext:
    """Establish a trace context from trace ID and span ID.
    
    Note: This is a legacy function. Consider using extract_trace_context()
    or start_span_with_remote_parent() for better OpenTelemetry integration.

    Args:
        trace_id: The trace ID from the parent request (32 hex characters)
        parent_span_id: The span ID of the parent span (16 hex characters)
        clear_existing: Whether to clear existing context first (unused)

    Returns:
        OpenTelemetry SpanContext
    """
    # Create a fake traceparent header and use OpenTelemetry to parse it
    traceparent = f"00-{trace_id}-{parent_span_id}-01"
    span_context = get_span_context_from_headers(traceparent)
    
    if span_context:
        return span_context
    else:
        # Fallback to manual creation if parsing fails
        from opentelemetry.trace import SpanContext, TraceFlags
        return SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(parent_span_id, 16),
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED)
        )