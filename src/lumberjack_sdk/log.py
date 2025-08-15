"""
Logging utility module for Lumberjack.

This module provides logging context management functionality,
allowing creation and management of trace contexts.
"""
import inspect
import re
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sized, cast
from collections.abc import Mapping as ABMapping, Sequence as ABSequence
from opentelemetry import trace, context


from opentelemetry._logs import SeverityNumber  # type: ignore[attr-defined]
from opentelemetry.sdk._logs import LogRecord as SDKLogRecord  # type: ignore[attr-defined]

from .constants import (
    # Legacy constants for backward compatibility
    EXEC_TYPE_RESERVED_V2,
    EXEC_VALUE_RESERVED_V2,
    FILE_KEY_RESERVED_V2,
    FUNCTION_KEY_RESERVED_V2,
    LINE_KEY_RESERVED_V2,
    MESSAGE_KEY_RESERVED_V2,
    SOURCE_KEY_RESERVED_V2,
    SPAN_ID_KEY_RESERVED_V2,
    TRACE_ID_KEY_RESERVED_V2,
    TRACEBACK_KEY_RESERVED_V2,
)
# LoggingContext removed - using OpenTelemetry context directly
from .core import Lumberjack
from .internal_utils.fallback_logger import sdk_logger




masked_terms = {
    'password'
}

pattern = re.compile(
    r"(?P<db>[a-z\+]+)://(?P<user>[a-zA-Z0-9_-]+):(?P<pw>[a-zA-Z0-9_]+)@(?P<host>[\.a-zA-Z0-9_-]+):(?P<port>\d+)"
)


def _emit_to_otel_logger(message: str, level: str, log_data: Dict[str, Any]) -> None:
    """Emit log directly to OpenTelemetry logger.
    
    Args:
        message: The log message
        level: Log level (debug, info, warning, error, critical)
        log_data: Additional log data/attributes
    """
    lumberjack = Lumberjack()
    otel_logger = lumberjack.logger
    
    if not otel_logger:
        # No logger available (not initialized or in fallback mode)
        return
    
    # Map our log levels to OpenTelemetry severity
    level_map = {
        'debug': SeverityNumber.DEBUG,
        'info': SeverityNumber.INFO,
        'warning': SeverityNumber.WARN,
        'error': SeverityNumber.ERROR,
        'critical': SeverityNumber.FATAL
    }
    
    severity = level_map.get(level, SeverityNumber.INFO)
    
    # Remove message and level from attributes (they're handled separately in LogRecord)
    attributes = {k: v for k, v in log_data.items() 
                 if k not in (MESSAGE_KEY_RESERVED_V2, 'tb_rv2_level')}
    
    # Create SDK LogRecord with all required fields that OTLP/GRPC exporters expect
    # This includes resource, dropped_attributes, context, etc.
    now_ns = int(time.time_ns())
    
    log_record = SDKLogRecord(
        timestamp=now_ns,
        observed_timestamp=now_ns,  # When we observed/created this log
        context=context.get_current(),  # Current OpenTelemetry context
        severity_number=severity,
        body=message,
        resource=otel_logger.resource,  # Resource from the logger provider
        attributes=attributes
        # Note: dropped_attributes property is automatically available due to SDK LogRecord implementation
        # Note: trace_id, span_id, trace_flags are automatically extracted from context
    )
    otel_logger.emit(log_record)


class Log:
    """Logging utility class for managing trace contexts and stdout override."""

    @staticmethod
    def _prepare_log_data(message: str, data: Any = None, **kwargs: Dict[str, Any]) -> Dict[str, Any]:
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
            #locals_dict: Dict[str, Any] = {}

            # don't take a frame from the SDK wrapper
            for frame_info in inspect.stack():
                frame_file = frame_info.filename
                if "lumberjack" not in frame_file and "<frozen" not in frame_file:
                    filename = frame_file
                    line_number = frame_info.lineno
                    function_name = frame_info.function
                    # locals_dict = Log.extract_relevant_locals(
                    #     frame_info.frame.f_locals)
                    break

            # Start with empty log data (context now handled by OpenTelemetry)
            log_data: Dict[str, Any] = {}

            # log_data['f_locals'] = locals_dict

            # Merge explicit data dict if provided
            if data is not None and isinstance(data, dict):
                log_data.update(cast(Dict[str, Any], data))
            elif data is not None:
                log_data.update({'data': data})

            # Merge kwargs
            if kwargs:
                log_data.update(kwargs)

            # Create a new dictionary to avoid modifying in place
            processed_data: Dict[str, Any] = {}
            
            # Use OpenTelemetry semantic conventions as primary attributes
            if filename:
                processed_data['code.file.path'] = filename
                processed_data[FILE_KEY_RESERVED_V2] = filename  # Legacy compatibility
            if line_number:
                processed_data['code.line.number'] = line_number
                processed_data[LINE_KEY_RESERVED_V2] = line_number  # Legacy compatibility  
            if function_name:
                processed_data['code.function.name'] = function_name
                processed_data[FUNCTION_KEY_RESERVED_V2] = function_name  # Legacy compatibility
            
            # if we haven't set the source upstream, it's from our SDK
            if not log_data.get(SOURCE_KEY_RESERVED_V2):
                log_data[SOURCE_KEY_RESERVED_V2] = "lumberjack"

            for key, value in log_data.items():
                if value is None:
                    continue

                # sent from logger
                if key == 'msg_args':
                    processed_data[key] = value
                    continue

                # Handle exceptions - use OpenTelemetry semantic conventions as primary
                if isinstance(value, Exception):
                    # OpenTelemetry standard exception attributes (primary)
                    processed_data['exception.type'] = value.__class__.__name__
                    processed_data['exception.message'] = str(value)
                    if value.__traceback__ is not None:
                        processed_data['exception.stacktrace'] = '\n'.join(traceback.format_exception(
                            type(value), value, value.__traceback__))
                    
                    # Legacy keys for backward compatibility
                    processed_data[EXEC_TYPE_RESERVED_V2] = value.__class__.__name__
                    processed_data[EXEC_VALUE_RESERVED_V2] = str(value)
                    if value.__traceback__ is not None:
                        processed_data[TRACEBACK_KEY_RESERVED_V2] = '\n'.join(traceback.format_exception(
                            type(value), value, value.__traceback__))

                # Handle datetime objects - convert to timestamp
                elif isinstance(value, datetime):
                    processed_data[key] = int(value.timestamp())
                # Handle dictionaries - maintain their nested structure
                elif isinstance(value, dict):
                    processed_data[key] = {}
                    Log.recurse_and_collect_dict(cast(Mapping[str, Any], value), processed_data[key])
                # Handle complex objects - extract attributes
                elif isinstance(value, object) and not isinstance(value, (int, float, str, bool, type(None))):
                    processed_data[key] = {}
                    for attr_name in dir(value):
                        if not attr_name.startswith("_"):
                            try:
                                attr_value = getattr(value, attr_name)
                                if isinstance(attr_value, (int, float, str, bool, type(None))):
                                    if attr_value is None:
                                        processed_data[key][attr_name] = "None"
                                    # Mask password-related keys
                                    elif any(pw_key in attr_name.lower() for pw_key in masked_terms):
                                        processed_data[key][attr_name] = '*****'
                                    else:
                                        processed_data[key][attr_name] = attr_value
                            except:
                                continue
                # Handle primitive types
                else:
                    # Mask password-related keys
                    if any(pw_key in key.lower() for pw_key in masked_terms):
                        processed_data[key] = '*****'
                    elif isinstance(value, str) and "url" in key.lower():
                        processed_data[key] = pattern.sub(mask_pw, value)
                    else:
                        processed_data[key] = value

            # Check if we have automatic exception info available and not already processed
            if 'exception.stacktrace' not in processed_data:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exc_type and exc_value and exc_traceback:
                    # OpenTelemetry semantic conventions (primary)
                    processed_data['exception.type'] = exc_type.__name__
                    processed_data['exception.message'] = str(exc_value)
                    processed_data['exception.stacktrace'] = ''.join(traceback.format_exception(
                        exc_type, exc_value, exc_traceback))
                    
                    # Legacy keys for backward compatibility
                    processed_data[EXEC_TYPE_RESERVED_V2] = exc_type.__name__
                    processed_data[EXEC_VALUE_RESERVED_V2] = str(exc_value)
                    processed_data[TRACEBACK_KEY_RESERVED_V2] = ''.join(traceback.format_exception(
                        exc_type, exc_value, exc_traceback))

            # Add trace context for legacy compatibility (OpenTelemetry LogRecord handles this automatically)

            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                span_context = current_span.get_span_context()
                if span_context.is_valid:
                    # Legacy keys for backward compatibility only
                    processed_data[SPAN_ID_KEY_RESERVED_V2] = format(span_context.span_id, "016x")
                    processed_data[TRACE_ID_KEY_RESERVED_V2] = format(span_context.trace_id, "032x")

            return processed_data
        except Exception as e:
            sdk_logger.error(
                f"Error in Log._prepare_log_data : {str(e)}: {traceback.format_exc()}")
            return {}

    @staticmethod
    def debug(message: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """Log a debug message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            _emit_to_otel_logger(message, 'debug', log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.debug : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def info(message: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """Log an info message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            _emit_to_otel_logger(message, 'info', log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.info : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def warning(message: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """Log a warning message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            _emit_to_otel_logger(message, 'warning', log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.warning : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def warn(message: str,data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """alias for warning

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            Log.warning(message, data, **kwargs)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.warn : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def error(message: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """Log an error message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            _emit_to_otel_logger(message, 'error', log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.error : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def critical(message: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """Log a critical message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            _emit_to_otel_logger(message, 'critical', log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.critical : {str(e)}: {traceback.format_exc()}")


    @staticmethod
    def recurse_and_collect_dict(
        data: Mapping[str, Any],
        collector: Dict[str, Any],
        prefix: str = "",
    ) -> Dict[str, Any]:
        """
        Process dictionary values while preserving structure. Handles masking of sensitive values,
        URL obfuscation, and proper handling of null/None values.
        """
        def process_scalar(k: str, v: Any, key_prefix: Optional[str] = None) -> Any:
            # Handle None explicitly as string "None"
            if v is None:
                return "None"
            # Mask if key or prefix matches masked terms
            k_lower = k.lower()
            if any(pw in k_lower for pw in masked_terms) or (
                key_prefix is not None and any(pw in key_prefix.lower() for pw in masked_terms)
            ):
                return "*****"
            # Obfuscate URLs if string and key contains "url"
            if isinstance(v, str) and "url" in k_lower:
                return pattern.sub(mask_pw, v)
            return v

        at_root = not prefix
        for key, value in data.items():
            if isinstance(value, ABMapping):
                child: Dict[str, Any] = {}
                collector[key] = child
                next_prefix = key if at_root else f"{prefix}_{key}"
                Log.recurse_and_collect_dict(cast(Mapping[str, Any], value), child, next_prefix)

            elif isinstance(value, ABSequence) and not isinstance(value, (str, bytes, bytearray)):
                sized_value = cast(Sized, value)
                collector[f"{key}_count"] = len(sized_value)

            elif isinstance(value, (str, int, float, bool, type(None))):
                collector[key] = process_scalar(key, value, None if at_root else prefix)

            else:
                # Optional: handle other container types (set/tuple) if desired
                collector[key] = value

        return collector





def mask_pw(match: re.Match[str]):
    return f"{match.group('db')}://{match.group('user')}:*****@{match.group('host')}:{match.group('port')}"


