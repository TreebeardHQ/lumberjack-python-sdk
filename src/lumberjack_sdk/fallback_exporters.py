"""
Fallback exporters for Lumberjack SDK.

These exporters are used in fallback mode when no API key is provided,
allowing logs and traces to still be captured and output locally.
"""
from typing import Sequence

from opentelemetry.sdk._logs.export import LogExporter, LogExportResult  # type: ignore[attr-defined]
from opentelemetry.sdk._logs import LogData  # type: ignore[attr-defined]

from .internal_utils.fallback_logger import fallback_logger
from .constants import (
    TRACE_ID_KEY_RESERVED_V2,
    SPAN_ID_KEY_RESERVED_V2, 
    MESSAGE_KEY_RESERVED_V2,
    LEVEL_KEY_RESERVED_V2,
    ERROR_KEY_RESERVED_V2,
    TS_KEY_RESERVED_V2,
    FILE_KEY_RESERVED_V2,
    LINE_KEY_RESERVED_V2,
    FUNCTION_KEY_RESERVED_V2,
    TRACEBACK_KEY_RESERVED_V2,
    TRACE_NAME_KEY_RESERVED_V2,
    SOURCE_KEY_RESERVED_V2,
    EXEC_TYPE_RESERVED_V2,
    EXEC_VALUE_RESERVED_V2
)


class FallbackLogExporter(LogExporter):
    """Simple log exporter that outputs to fallback logger for fallback mode."""
    
    def export(self, batch: Sequence[LogData]) -> LogExportResult:
        """Export logs to fallback logger."""
        try:
            for log_data in batch:
                log_record = log_data.log_record
                
                # Get severity info - prefer text, fallback to mapping from number
                severity_text = log_record.severity_text 
                if not severity_text and log_record.severity_number:
                    severity_text = self._severity_number_to_text(log_record.severity_number)
                severity_text = severity_text or 'INFO'
                
                message = f"{log_record.body or ''}"
                
                # Add trace info right after message (grayed out)
                trace_info = ""
                if log_record.span_id and log_record.trace_id:
                    gray = '\033[90m'
                    reset = '\033[0m'
                    trace_info = f" {gray}[{log_record.span_id:016x}|{log_record.trace_id:032x}]{reset}"
                
                attrs_str = ""
                if log_record.attributes:
                    # Add key attributes to message with pretty names (uncolored)
                    pretty_attrs = []
                    stacktrace = None
                    
                    for k, v in log_record.attributes.items():
                        if k not in ['otelSpanID', 'otelTraceID', 'otelTraceSampled', 'otelServiceName']:
                            pretty_key = self._prettify_attribute_name(k)
                            
                            # Skip our own trace/span IDs since we're handling them separately
                            if pretty_key in ['trace_id', 'span_id']:
                                continue
                                
                            # Handle stacktrace specially - format it nicely
                            # Support both OpenTelemetry semantic conventions and legacy keys
                            if pretty_key in ['traceback', 'exception.stacktrace'] and v:
                                stacktrace = self._format_stacktrace(v)
                            else:
                                pretty_attrs.append(f"{pretty_key}={v}")
                    
                    if pretty_attrs:
                        gray = '\033[90m'
                        reset = '\033[0m'
                        attrs_str = f" {gray}| {', '.join(pretty_attrs)}{reset}"
                    
                    # Add formatted stacktrace at the end if present
                    if stacktrace:
                        attrs_str += f"\n{stacktrace}"
                
                # Add color coding only to the main message, then add trace info and attrs
                colored_message = self._colorize_message(message, severity_text) + trace_info + attrs_str
                
                # Use fallback logger with appropriate level
                self._log_at_appropriate_level(colored_message, severity_text)
            
            return LogExportResult.SUCCESS
        except Exception as e:
            fallback_logger.error(f"Error in FallbackLogExporter: {e}")
            return LogExportResult.FAILURE
    
    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass
    
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending logs."""
        return True
    
    def _log_at_appropriate_level(self, message: str, severity_text: str) -> None:
        """Log message using the appropriate fallback logger level."""
        # Map OpenTelemetry severity to Python logging levels
        severity = (severity_text or 'INFO').upper()
        
        if severity in ['TRACE', 'DEBUG']:
            fallback_logger.debug(message)
        elif severity == 'INFO':
            fallback_logger.info(message)
        elif severity in ['WARN', 'WARNING']:
            fallback_logger.warning(message)
        elif severity == 'ERROR':
            fallback_logger.error(message)
        elif severity in ['FATAL', 'CRITICAL']:
            fallback_logger.critical(message)
        else:
            # Default to info for unknown levels
            fallback_logger.info(message)
    
    def _severity_number_to_text(self, severity_number) -> str:
        """Convert OpenTelemetry severity number to text."""
        from opentelemetry._logs import SeverityNumber
        
        if hasattr(severity_number, 'value'):
            value = severity_number.value
        else:
            value = int(severity_number)
            
        # OpenTelemetry severity number mappings
        if value <= 4:  # TRACE
            return "TRACE"
        elif value <= 8:  # DEBUG  
            return "DEBUG"
        elif value <= 12:  # INFO
            return "INFO"
        elif value <= 16:  # WARN
            return "WARN"
        elif value <= 20:  # ERROR
            return "ERROR"
        else:  # FATAL
            return "FATAL"
    
    def _prettify_attribute_name(self, attr_name: str) -> str:
        """Convert internal attribute names to readable names."""
        # Map of internal reserved keys to pretty names
        pretty_names = {
            # Legacy Lumberjack attributes
            TRACE_ID_KEY_RESERVED_V2: 'trace_id',
            SPAN_ID_KEY_RESERVED_V2: 'span_id',
            MESSAGE_KEY_RESERVED_V2: 'message',
            LEVEL_KEY_RESERVED_V2: 'level',
            ERROR_KEY_RESERVED_V2: 'error',
            TS_KEY_RESERVED_V2: 'timestamp',
            FILE_KEY_RESERVED_V2: 'file',
            LINE_KEY_RESERVED_V2: 'line',
            FUNCTION_KEY_RESERVED_V2: 'function',
            TRACEBACK_KEY_RESERVED_V2: 'traceback',
            TRACE_NAME_KEY_RESERVED_V2: 'trace_name',
            SOURCE_KEY_RESERVED_V2: 'source',
            EXEC_TYPE_RESERVED_V2: 'exec_type',
            EXEC_VALUE_RESERVED_V2: 'exec_value',
            # OpenTelemetry semantic conventions (already pretty, but maintain consistency)
            'code.file.path': 'code.file.path',
            'code.line.number': 'code.line.number', 
            'code.function.name': 'code.function.name',
            'exception.type': 'exception.type',
            'exception.message': 'exception.message',
            'exception.stacktrace': 'exception.stacktrace',
        }
        return pretty_names.get(attr_name, attr_name)
    
    def _format_stacktrace(self, stacktrace: str) -> str:
        """Format stacktrace for better readability with red coloring."""
        if not stacktrace or not isinstance(stacktrace, str):
            return ""
        
        # ANSI color codes for red text
        red = '\033[31m'
        reset = '\033[0m'
        
        lines = stacktrace.strip().split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.rstrip()
            if not line:
                continue
                
            # Add indentation and red coloring for better visual structure
            if line.startswith('  File '):
                # File references - make them stand out slightly
                formatted_lines.append(f"    {red}{line}{reset}")
            elif line.startswith('    '):
                # Code lines - add extra indentation
                formatted_lines.append(f"      {red}{line.strip()}{reset}")
            elif line.startswith('Traceback '):
                # Traceback header
                formatted_lines.append(f"  {red}{line}{reset}")
            else:
                # Exception messages and other lines
                formatted_lines.append(f"    {red}{line}{reset}")
        
        return '\n'.join(formatted_lines)
    
    def _colorize_message(self, message: str, severity: str) -> str:
        """Add color codes to log message based on severity."""
        # ANSI color codes
        colors = {
            'TRACE': '\033[90m',    # Dark gray
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARN': '\033[33m',     # Yellow
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'FATAL': '\033[35m',    # Magenta
            'CRITICAL': '\033[35m', # Magenta
        }
        reset = '\033[0m'
        
        color = colors.get(severity.upper(), '')
        return f"{color}{message}{reset}" if color else message