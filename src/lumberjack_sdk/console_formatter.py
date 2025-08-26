"""
Console formatter for Lumberjack SDK.

This module provides a custom logging formatter that displays log messages
in a clean format with extra attributes as JSON and proper exception handling.
"""
import json
import logging
from typing import Any, Dict


class LumberjackConsoleFormatter(logging.Formatter):
    """
    Custom formatter that displays log messages with extra attributes as JSON.
    
    Features:
    - Standard log format: timestamp [level] logger: message
    - Extra attributes displayed as compact JSON
    - Full exception tracebacks when exc_info is present
    - Filters out internal OpenTelemetry and SDK attributes
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record with extra attributes and exception info.
        
        Args:
            record: The LogRecord to format
            
        Returns:
            Formatted log message string
        """
        # Format the basic message using the parent formatter
        formatted_message = super().format(record)
        
        # Handle exception info properly (like standard formatter does)
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if formatted_message[-1:] != "\n":
                formatted_message = formatted_message + "\n"
            formatted_message = formatted_message + record.exc_text
        
        # Add extra attributes as JSON
        extras = self._get_extra_attributes(record)
        if extras:
            json_attrs = self._format_extras(extras)
            formatted_message += f" {json_attrs}"
        
        return formatted_message
    
    def _get_extra_attributes(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Extract extra attributes from a log record.
        
        Filters out standard logging attributes and internal SDK attributes.
        
        Args:
            record: The LogRecord to extract attributes from
            
        Returns:
            Dictionary of extra attributes
        """
        # Standard logging attributes that shouldn't be shown as "extra"
        standard_attrs = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 
            'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'message', 'exc_info',
            'exc_text', 'stack_info', 'asctime', 'taskName', 'getMessage'
        }
        
        # Get extra attributes (user-provided data)
        extras = {}
        for key, value in record.__dict__.items():
            if (key not in standard_attrs and 
                not key.startswith('_') and 
                not key.startswith('otel') and 
                not key.startswith('tb_rv2_')):
                extras[key] = value
        
        return extras
    
    def _format_extras(self, extras: Dict[str, Any]) -> str:
        """
        Format extra attributes as JSON string.
        
        Args:
            extras: Dictionary of extra attributes
            
        Returns:
            JSON formatted string, or string representation as fallback
        """
        try:
            return json.dumps(extras, separators=(',', ':'), default=str)
        except (TypeError, ValueError):
            # Fallback if JSON serialization fails (circular refs, etc.)
            return str(extras)