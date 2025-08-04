"""
OpenTelemetry migration module.

This module provides a way to switch between the legacy implementation
and the new OTEL-based implementation.
"""
import os
from typing import Any

# Check if OTEL migration is enabled
ENABLE_OTEL = os.getenv('LUMBERJACK_ENABLE_OTEL', 'false').lower() == 'true'


def get_implementation() -> dict:
    """Get the appropriate implementation based on configuration.
    
    Returns:
        Dictionary containing the implementation classes and functions
    """
    if ENABLE_OTEL:
        # Import OTEL-based implementations
        from .otel_core import OTelLumberjack as Lumberjack
        from .otel_context import OTelLoggingContext as LoggingContext
        from .otel_log import OTelLog as Log, initialize_otel_logging
        from .otel_span import (
            start_span, end_span, get_current_span, get_current_trace_id,
            set_span_attribute, add_span_event, record_exception_on_span, span_context
        )
        from .otel_flask import OTelLumberjackFlask as LumberjackFlask
        
        return {
            'Lumberjack': Lumberjack,
            'LoggingContext': LoggingContext,
            'Log': Log,
            'start_span': start_span,
            'end_span': end_span,
            'get_current_span': get_current_span,
            'get_current_trace_id': get_current_trace_id,
            'set_span_attribute': set_span_attribute,
            'add_span_event': add_span_event,
            'record_exception_on_span': record_exception_on_span,
            'span_context': span_context,
            'LumberjackFlask': LumberjackFlask,
            'initialize_otel_logging': initialize_otel_logging,
        }
    else:
        # Import legacy implementations
        from .core import Lumberjack
        from .context import LoggingContext
        from .log import Log
        from .span import (
            start_span, end_span, get_current_span, get_current_trace_id,
            set_span_attribute, add_span_event, record_exception_on_span, span_context
        )
        from .lumberjack_flask import LumberjackFlask
        
        return {
            'Lumberjack': Lumberjack,
            'LoggingContext': LoggingContext,
            'Log': Log,
            'start_span': start_span,
            'end_span': end_span,
            'get_current_span': get_current_span,
            'get_current_trace_id': get_current_trace_id,
            'set_span_attribute': set_span_attribute,
            'add_span_event': add_span_event,
            'record_exception_on_span': record_exception_on_span,
            'span_context': span_context,
            'LumberjackFlask': LumberjackFlask,
            'initialize_otel_logging': lambda *args, **kwargs: None,  # No-op for legacy
        }


# Get the current implementation
_impl = get_implementation()

# Export the appropriate implementations
Lumberjack = _impl['Lumberjack']
LoggingContext = _impl['LoggingContext']
Log = _impl['Log']
start_span = _impl['start_span']
end_span = _impl['end_span']
get_current_span = _impl['get_current_span']
get_current_trace_id = _impl['get_current_trace_id']
set_span_attribute = _impl['set_span_attribute']
add_span_event = _impl['add_span_event']
record_exception_on_span = _impl['record_exception_on_span']
span_context = _impl['span_context']
LumberjackFlask = _impl['LumberjackFlask']
initialize_otel_logging = _impl['initialize_otel_logging']