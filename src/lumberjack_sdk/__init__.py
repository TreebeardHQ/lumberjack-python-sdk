"""
Lumberjack - A Python observability library
"""

from opentelemetry.trace import SpanKind
from opentelemetry.trace import Status as SpanStatus
from opentelemetry.trace import StatusCode as SpanStatusCode

# LoggingContext removed - using OpenTelemetry context directly
from .core import Lumberjack
from .log import Log
from .lumberjack_flask import LumberjackFlask
from .lumberjack_fastapi import LumberjackFastAPI
from .lumberjack_trace import lumberjack_trace
from .span import (
    end_span,
    get_current_span,
    get_current_trace_id,
    record_exception_on_span,
    span_context,
    start_span,
)
from .trace_helpers import (
    establish_trace_context,
    extract_trace_context,
    get_span_context_from_headers,
    inject_trace_context,
    parse_traceparent,
    start_span_with_remote_parent,
)
from .version import __version__
from .metrics import (
    MetricsAPI,
    REDMetrics,
    get_meter,
    create_counter,
    create_histogram,
    create_up_down_counter,
    create_red_metrics,
)

__all__ = [
    "Lumberjack", "Log",
    "LumberjackFlask", "LumberjackFastAPI", "lumberjack_trace",
    "start_span", "end_span", "span_context", "get_current_span", "get_current_trace_id",
    "record_exception_on_span", "SpanKind", "SpanStatus", "SpanStatusCode",
    "extract_trace_context", "get_span_context_from_headers", "inject_trace_context", 
    "start_span_with_remote_parent", "parse_traceparent", "establish_trace_context",
    "__version__",
    # Metrics exports
    "MetricsAPI", "REDMetrics", "get_meter", "create_counter", "create_histogram",
    "create_up_down_counter", "create_red_metrics",
]
