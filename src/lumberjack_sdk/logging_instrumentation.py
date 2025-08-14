"""
OpenTelemetry logging instrumentation for Lumberjack.

This module handles the integration between Python's logging module and OpenTelemetry,
providing automatic trace correlation and log forwarding.
"""
import logging
from typing import Optional


from opentelemetry.instrumentation.logging import LoggingInstrumentor # type: ignore[attr-defined]
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry import _logs as logs  # type: ignore[attr-defined]

from .internal_utils.fallback_logger import sdk_logger


class LumberjackLoggingHandler(LoggingHandler):
    """Custom LoggingHandler that filters out Lumberjack SDK internal logs."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out logs from Lumberjack SDK itself to avoid loops."""
        # Don't forward our own SDK logs
        if record.name.startswith('lumberjack'):
            return False
        # Call parent filter method (LoggingHandler doesn't have a filter method, so use Handler's)
        return True





class LoggingInstrumentation:
    """Manages Python logging instrumentation for Lumberjack."""
    
    _instance: Optional['LoggingInstrumentation'] = None
    
    def __new__(cls) -> 'LoggingInstrumentation':
        """Singleton pattern to ensure only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize instance variables if not already initialized."""
        if not hasattr(self, '_otel_instrumentor'):
            self._otel_instrumentor: Optional[LoggingInstrumentor] = None
            self._otel_handler: Optional[LumberjackLoggingHandler] = None
            self._is_enabled: bool = False
    
    def enable(self, level: int = logging.DEBUG, logger_name: Optional[str] = None) -> None:
        """
        Enable Python logging forwarding to OpenTelemetry.
        
        This does two things:
        1. Adds trace_id, span_id, and other trace context to Python log records
        2. Forwards Python logs to OpenTelemetry for export through Lumberjack
        
        Args:
            level: The minimum logging level to capture (default: DEBUG)
            logger_name: Specific logger name to attach to, or None for root logger
        """
        if self._is_enabled:
            sdk_logger.debug("Python logging instrumentation already enabled")
            return
            
        # Get the logger provider to check if OpenTelemetry is set up
        logger_provider = logs.get_logger_provider()
        if not logger_provider:
            sdk_logger.warning("No OpenTelemetry logger provider found, Python log forwarding disabled")
            return
            
        # Check if we have a real LoggerProvider (not a proxy/fallback)  
        from opentelemetry.sdk._logs import LoggerProvider
        if not isinstance(logger_provider, LoggerProvider):
            sdk_logger.debug(f"Logger provider is {type(logger_provider)}, not a real LoggerProvider. Python log forwarding disabled.")
            return
            
        try:
            # 1. Enable trace context injection using LoggingInstrumentor
            if not self._otel_instrumentor:
                self._otel_instrumentor = LoggingInstrumentor()
                self._otel_instrumentor.instrument(
                    set_logging_format=False,  # Don't override format, just inject context
                    log_level=level
                )
                sdk_logger.debug("OpenTelemetry trace context injection enabled")
            
            # 2. Add LoggingHandler to forward logs to OpenTelemetry
            if not self._otel_handler:
                # Create a custom handler that filters out our own SDK logs
                self._otel_handler = LumberjackLoggingHandler(
                    level=level,
                    logger_provider=logger_provider
                )
                
                # Get the target logger
                target_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
                target_logger.addHandler(self._otel_handler)
                target_logger.setLevel(level)
                
                sdk_logger.debug(
                    f"OpenTelemetry log forwarding enabled for logger '{logger_name or 'root'}' at level: {logging.getLevelName(level)}"
                )
            
            self._is_enabled = True
            
        except Exception as e:
            sdk_logger.warning(f"Failed to enable OpenTelemetry logging instrumentation: {e}")
        
       
    
    def disable(self, logger_name: Optional[str] = None) -> None:
        """
        Disable forwarding of Python logger messages to Lumberjack.
        
        Args:
            logger_name: Specific logger name to detach from, or None for root logger
        """
        if not self._is_enabled:
            return
            
        try:
            # 1. Remove the LoggingHandler from Python's logger
            if self._otel_handler:
                target_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
                target_logger.removeHandler(self._otel_handler)
                self._otel_handler = None
                sdk_logger.debug(f"OpenTelemetry log forwarding disabled for logger '{logger_name or 'root'}'")
            
            # 2. Disable trace context injection
            if self._otel_instrumentor:
                self._otel_instrumentor.uninstrument()
                self._otel_instrumentor = None
                sdk_logger.debug("OpenTelemetry trace context injection disabled")
                
            self._is_enabled = False
            
        except Exception as e:
            sdk_logger.warning(f"Failed to disable OpenTelemetry logging instrumentation: {e}")
        
      
    
    def is_enabled(self) -> bool:
        """
        Return whether Python logger forwarding is currently enabled.
        
        Returns:
            True if Python logger forwarding is enabled, False otherwise
        """
        return self._is_enabled and (self._otel_handler is not None or self._otel_instrumentor is not None)


# Global singleton instance
_logging_instrumentation = LoggingInstrumentation()


def enable_python_logger_forwarding(level: int = logging.DEBUG, 
                                   logger_name: Optional[str] = None) -> None:
    """
    Enable forwarding of Python logger messages to Lumberjack.
    
    Args:
        level: The minimum logging level to capture (default: DEBUG)
        logger_name: Specific logger name to attach to, or None for root logger
    """
    _logging_instrumentation.enable(level, logger_name)


def disable_python_logger_forwarding(logger_name: Optional[str] = None) -> None:
    """
    Disable forwarding of Python logger messages to Lumberjack.
    
    Args:
        logger_name: Specific logger name to detach from, or None for root logger
    """
    _logging_instrumentation.disable(logger_name)


def is_python_logger_forwarding_enabled() -> bool:
    """
    Return whether Python logger forwarding is currently enabled.
    
    Returns:
        True if Python logger forwarding is enabled, False otherwise
    """
    return _logging_instrumentation.is_enabled()