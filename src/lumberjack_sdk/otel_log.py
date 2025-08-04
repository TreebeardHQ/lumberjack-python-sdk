"""
OpenTelemetry-based logging functionality for Lumberjack.

This module provides the same Log interface but uses OpenTelemetry's
logging system internally.
"""
import inspect
import logging
import os
import re
import sys
import threading
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, TextIO

from opentelemetry import _logs
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from .constants import (
    EXEC_TYPE_RESERVED_V2,
    EXEC_VALUE_RESERVED_V2,
    FILE_KEY_RESERVED_V2,
    FUNCTION_KEY_RESERVED_V2,
    LEVEL_KEY_RESERVED_V2,
    LINE_KEY_RESERVED_V2,
    MESSAGE_KEY_RESERVED_V2,
    SOURCE_KEY_RESERVED_V2,
    SPAN_ID_KEY_RESERVED_V2,
    TAGS_KEY,
    TRACE_COMPLETE_ERROR_MARKER,
    TRACE_COMPLETE_SUCCESS_MARKER,
    TRACE_ID_KEY_RESERVED_V2,
    TRACE_NAME_KEY_RESERVED_V2,
    TRACE_START_MARKER,
    TRACEBACK_KEY_RESERVED_V2,
    TS_KEY,
)
from .otel_context import OTelLoggingContext
from .internal_utils.fallback_logger import sdk_logger


# Level mapping from Python logging to Lumberjack
level_map = {
    logging.DEBUG: 'debug',
    logging.INFO: 'info',
    logging.WARNING: 'warning',
    logging.WARN: 'warning',  # deprecated but still used
    logging.ERROR: 'error',
    logging.CRITICAL: 'critical',
    logging.FATAL: 'critical'  # alias for CRITICAL
}

# Reverse mapping for OTEL severity
lumberjack_to_logging_level = {
    'trace': logging.DEBUG,
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

# Global OTEL logger instance
_otel_logger: Optional[Any] = None

# Global handler instance for Python logger forwarding
_lumberjack_handler: Optional[LoggingHandler] = None

# Thread-local guard to prevent recursive logging
_handler_guard = threading.local()

# Masked terms for sensitive data
masked_terms = {
    'password'
}

pattern = re.compile(
    r"(?P<db>[a-z\+]+)://(?P<user>[a-zA-Z0-9_-]+):(?P<pw>[a-zA-Z0-9_]+)@(?P<host>[\.a-zA-Z0-9_-]+):(?P<port>\d+)"
)


def initialize_otel_logging(
    log_exporter: Any,
    resource: Optional[Resource] = None
) -> None:
    """Initialize OpenTelemetry logging system.
    
    Args:
        log_exporter: The log exporter to use (e.g., LumberjackLogExporter)
        resource: Optional resource information
    """
    global _otel_logger
    
    # Create LoggerProvider if not already set
    if get_logger_provider() is None or not hasattr(get_logger_provider(), '_real_logger_provider'):
        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)
    else:
        logger_provider = get_logger_provider()
    
    # Add the log record processor with our custom exporter
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )
    
    # Get logger for direct logging
    _otel_logger = logger_provider.get_logger(__name__)
    
    # Start the exporter worker if it has one
    if hasattr(log_exporter, 'start_worker'):
        log_exporter.start_worker()


def enable_python_logger_forwarding(
    level: int = logging.DEBUG,
    logger_name: Optional[str] = None
) -> None:
    """Enable forwarding of Python logger messages to OTEL.
    
    Args:
        level: Minimum logging level to capture
        logger_name: Name of logger to attach to (None for root logger)
    """
    global _lumberjack_handler
    
    if _lumberjack_handler is not None:
        return  # Already enabled
    
    # Get the logger provider
    logger_provider = get_logger_provider()
    if logger_provider is None:
        sdk_logger.warning("OTEL LoggerProvider not initialized, cannot enable Python logger forwarding")
        return
    
    # Create and configure the OTEL logging handler
    _lumberjack_handler = LoggingHandler(
        level=level,
        logger_provider=logger_provider
    )
    
    # Get the target logger
    target_logger = logging.getLogger(logger_name)
    target_logger.addHandler(_lumberjack_handler)
    target_logger.setLevel(level)
    
    # Also enable OTEL logging instrumentation for trace correlation
    try:
        LoggingInstrumentor().instrument(set_logging_format=True)
    except Exception as e:
        sdk_logger.debug(f"Could not enable OTEL logging instrumentation: {e}")


def enable_stdout_override() -> None:
    """Enable stdout capture and redirect to OTEL logging."""
    # Store original stdout
    original_stdout = sys.stdout
    original_write = original_stdout.write
    
    def lumberjack_write(text: str) -> int:
        # Call the original write first
        result = original_write(text)
        
        # Skip empty strings and newlines
        if text.strip():
            # Avoid infinite recursion by checking for SDK logs
            if not getattr(_handler_guard, 'processing', False):
                _handler_guard.processing = True
                try:
                    OTelLog.info(text.strip(), {SOURCE_KEY_RESERVED_V2: "stdout"})
                finally:
                    _handler_guard.processing = False
        
        return result
    
    # Replace stdout.write
    sys.stdout.write = lumberjack_write


class OTelLog:
    """OpenTelemetry-based logging utility class."""

    @staticmethod
    def _prepare_log_data(message: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Prepare log data by merging context, provided data and kwargs.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments

        Returns:
            Dict containing the complete log entry
        """
        try:
            filename = None
            line_number = None
            function_name = None

            # Don't take a frame from the SDK wrapper
            for frame_info in inspect.stack():
                frame_file = frame_info.filename
                if "lumberjack" not in frame_file and "<frozen" not in frame_file:
                    filename = frame_file
                    line_number = frame_info.lineno
                    function_name = frame_info.function
                    break

            # Start with the context data
            log_data = OTelLoggingContext.get_all()

            # Add the message
            log_data[MESSAGE_KEY_RESERVED_V2] = message

            # Merge explicit data dict if provided
            if data is not None and isinstance(data, dict):
                log_data.update(data)
            elif data is not None:
                log_data.update({'data': data})

            # Merge kwargs
            if kwargs:
                log_data.update(kwargs)

            # Create a new dictionary to avoid modifying in place
            processed_data = {}
            processed_data[FILE_KEY_RESERVED_V2] = filename
            processed_data[LINE_KEY_RESERVED_V2] = line_number
            processed_data[FUNCTION_KEY_RESERVED_V2] = function_name
            
            # If we haven't set the source upstream, it's from our SDK
            if not log_data.get(SOURCE_KEY_RESERVED_V2):
                log_data[SOURCE_KEY_RESERVED_V2] = "lumberjack"

            for key, value in log_data.items():
                if value is None:
                    continue

                # Handle exceptions - these get special treatment with traceback extraction
                if isinstance(value, Exception):
                    processed_data[EXEC_TYPE_RESERVED_V2] = value.__class__.__name__
                    processed_data[EXEC_VALUE_RESERVED_V2] = str(value)
                    if value.__traceback__ is not None:
                        processed_data[TRACEBACK_KEY_RESERVED_V2] = '\n'.join(
                            traceback.format_exception(type(value), value, value.__traceback__)
                        )

                # Handle datetime objects - convert to timestamp
                elif isinstance(value, datetime):
                    processed_data[key] = int(value.timestamp())
                
                # Mask sensitive data
                elif isinstance(value, str):
                    processed_data[key] = OTelLog.mask_sensitive_data(value)
                
                # Handle other types
                else:
                    processed_data[key] = value

            # Add trace context from OTEL
            trace_id = OTelLoggingContext.get_trace_id()
            span_id = OTelLoggingContext.get_span_id()
            
            if trace_id:
                processed_data[TRACE_ID_KEY_RESERVED_V2] = trace_id
            if span_id:
                processed_data[SPAN_ID_KEY_RESERVED_V2] = span_id

            # Add timestamp
            processed_data[TS_KEY] = round(datetime.now().timestamp() * 1000)

            return processed_data

        except Exception as e:
            sdk_logger.error(f"Error preparing log data: {e}")
            return {
                MESSAGE_KEY_RESERVED_V2: message,
                TS_KEY: round(datetime.now().timestamp() * 1000)
            }

    @staticmethod
    def mask_sensitive_data(text: str) -> str:
        """Mask sensitive data in text."""
        for term in masked_terms:
            if term.lower() in text.lower():
                text = re.sub(
                    f'({term}["\']?\\s*[:=]\\s*["\']?)([^"\'\\s,}}]+)',
                    r'\1***',
                    text,
                    flags=re.IGNORECASE
                )
        
        # Mask database URLs
        text = pattern.sub(r'\g<db>://\g<user>:***@\g<host>:\g<port>', text)
        return text

    @staticmethod
    def _log(level: str, message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Internal method to log via OTEL."""
        global _otel_logger
        
        if _otel_logger is None:
            # Fall back to SDK logger if OTEL not initialized
            sdk_logger.log(lumberjack_to_logging_level.get(level, logging.INFO), message)
            return

        # Prepare log data
        log_data = OTelLog._prepare_log_data(message, data, **kwargs)
        
        # Extract the message and convert the rest to attributes
        body = log_data.pop(MESSAGE_KEY_RESERVED_V2, message)
        
        # Create LogRecord and emit via OTEL
        from opentelemetry.sdk._logs import LogRecord
        import time
        
        log_record = LogRecord(
            timestamp=int(time.time_ns()),
            body=body,
            severity_number=_get_otel_severity_number(level),
            attributes=log_data
        )
        _otel_logger.emit(log_record)

    @staticmethod
    def trace(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a trace message."""
        OTelLog._log('trace', message, data, **kwargs)

    @staticmethod
    def debug(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a debug message."""
        OTelLog._log('debug', message, data, **kwargs)

    @staticmethod
    def info(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log an info message."""
        OTelLog._log('info', message, data, **kwargs)

    @staticmethod
    def warning(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a warning message."""
        OTelLog._log('warning', message, data, **kwargs)

    @staticmethod
    def error(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log an error message."""
        OTelLog._log('error', message, data, **kwargs)

    @staticmethod
    def critical(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a critical message."""
        OTelLog._log('critical', message, data, **kwargs)

    @staticmethod
    def enable_python_logger_forwarding(
        level: int = logging.DEBUG,
        logger_name: Optional[str] = None
    ) -> None:
        """Enable forwarding of Python logger messages to OTEL."""
        enable_python_logger_forwarding(level, logger_name)

    @staticmethod
    def enable_stdout_override() -> None:
        """Enable stdout capture and redirect to OTEL logging."""
        enable_stdout_override()


def _get_otel_severity_number(level: str) -> int:
    """Map Lumberjack level to OTEL severity number."""
    severity_map = {
        'trace': 1,
        'debug': 5,
        'info': 9,
        'warning': 13,
        'error': 17,
        'critical': 21
    }
    return severity_map.get(level, 9)  # Default to INFO


# Backward compatibility - alias OTelLog as Log
Log = OTelLog