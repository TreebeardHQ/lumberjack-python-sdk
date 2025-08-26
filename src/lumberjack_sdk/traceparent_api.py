"""
Traceparent API for retrieving W3C trace context information.

This module provides simple APIs to get the current trace context in the
W3C traceparent format from active OpenTelemetry spans.
"""
from typing import Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanContext, TraceFlags


def get_current_traceparent() -> Optional[str]:
    """Get the current W3C traceparent string from the active span.
    
    Returns the traceparent in the standard W3C format:
    00-{trace_id}-{span_id}-{flags}
    
    Returns:
        The W3C traceparent string if an active span exists, None otherwise
        
    Example:
        >>> traceparent = get_current_traceparent()
        >>> print(traceparent)
        '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
    """
    span = trace.get_current_span()
    if not span or not span.is_recording():
        return None
    
    span_context = span.get_span_context()
    if not span_context or not span_context.is_valid:
        return None
    
    # Format according to W3C spec
    version = "00"
    trace_id = format(span_context.trace_id, '032x')
    span_id = format(span_context.span_id, '016x')
    flags = format(span_context.trace_flags, '02x')
    
    return f"{version}-{trace_id}-{span_id}-{flags}"


def get_trace_context_info() -> Optional[Dict[str, str]]:
    """Get detailed trace context information from the active span.
    
    Returns a dictionary containing the trace context components:
    - traceparent: The full W3C traceparent string
    - trace_id: The 32-character hex trace ID
    - span_id: The 16-character hex span ID  
    - parent_span_id: The parent span ID if available
    - flags: The 2-character hex trace flags
    - is_sampled: Boolean indicating if the trace is sampled
    
    Returns:
        Dictionary with trace context details if an active span exists, None otherwise
        
    Example:
        >>> info = get_trace_context_info()
        >>> print(info)
        {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
            'trace_id': '4bf92f3577b34da6a3ce929d0e0e4736',
            'span_id': '00f067aa0ba902b7',
            'parent_span_id': None,
            'flags': '01',
            'is_sampled': True
        }
    """
    span = trace.get_current_span()
    if not span or not span.is_recording():
        return None
    
    span_context = span.get_span_context()
    if not span_context or not span_context.is_valid:
        return None
    
    trace_id = format(span_context.trace_id, '032x')
    span_id = format(span_context.span_id, '016x')
    flags = format(span_context.trace_flags, '02x')
    
    # Check if trace is sampled
    is_sampled = bool(span_context.trace_flags & TraceFlags.SAMPLED)
    
    # Get parent span ID if available
    parent_span_id = None
    parent_context = getattr(span, 'parent', None)
    if parent_context and isinstance(parent_context, SpanContext):
        if parent_context.is_valid:
            parent_span_id = format(parent_context.span_id, '016x')
    
    return {
        'traceparent': f"00-{trace_id}-{span_id}-{flags}",
        'trace_id': trace_id,
        'span_id': span_id,
        'parent_span_id': parent_span_id,
        'flags': flags,
        'is_sampled': is_sampled
    }


def format_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Format a W3C traceparent string from components.
    
    Args:
        trace_id: The 32-character hex trace ID
        span_id: The 16-character hex span ID
        sampled: Whether the trace is sampled (affects flags)
        
    Returns:
        Formatted W3C traceparent string
        
    Example:
        >>> traceparent = format_traceparent(
        ...     "4bf92f3577b34da6a3ce929d0e0e4736",
        ...     "00f067aa0ba902b7",
        ...     sampled=True
        ... )
        >>> print(traceparent)
        '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
    """
    # Validate inputs
    if len(trace_id) != 32:
        raise ValueError(f"trace_id must be 32 hex characters, got {len(trace_id)}")
    if len(span_id) != 16:
        raise ValueError(f"span_id must be 16 hex characters, got {len(span_id)}")
    
    # Validate hex format
    try:
        int(trace_id, 16)
        int(span_id, 16)
    except ValueError as e:
        raise ValueError(f"Invalid hex format: {e}")
    
    # Format flags (01 for sampled, 00 for not sampled)
    flags = "01" if sampled else "00"
    
    return f"00-{trace_id}-{span_id}-{flags}"


def parse_traceparent(traceparent: str) -> Optional[Dict[str, str]]:
    """Parse a W3C traceparent string into its components.
    
    Args:
        traceparent: The W3C traceparent string to parse
        
    Returns:
        Dictionary with parsed components or None if invalid
        
    Example:
        >>> components = parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
        >>> print(components)
        {
            'version': '00',
            'trace_id': '4bf92f3577b34da6a3ce929d0e0e4736',
            'span_id': '00f067aa0ba902b7',
            'flags': '01',
            'is_sampled': True
        }
    """
    parts = traceparent.strip().split('-')
    if len(parts) != 4:
        return None
    
    version, trace_id, span_id, flags = parts
    
    # Validate format
    if version != "00":
        return None  # Only support version 00
    if len(trace_id) != 32 or len(span_id) != 16 or len(flags) != 2:
        return None
        
    # Validate hex
    try:
        int(trace_id, 16)
        int(span_id, 16) 
        flags_int = int(flags, 16)
    except ValueError:
        return None
    
    return {
        'version': version,
        'trace_id': trace_id,
        'span_id': span_id,
        'flags': flags,
        'is_sampled': bool(flags_int & 0x01)
    }