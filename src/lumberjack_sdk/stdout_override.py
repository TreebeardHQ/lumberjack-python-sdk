"""
Stdout override functionality for capturing print statements.

This module provides functionality to intercept stdout (print statements) 
and log them through Lumberjack while still allowing normal output.
"""
import inspect
import sys
import threading
import time
from typing import Any, Dict, Optional, TextIO, Tuple

from opentelemetry import _logs as logs, context
from opentelemetry._logs import SeverityNumber
from opentelemetry.sdk._logs import LogRecord as SDKLogRecord

from .constants import SOURCE_KEY_RESERVED_V2
from .internal_utils.fallback_logger import sdk_logger


# Thread-local guard to prevent recursive printing
_guard = threading.local()


def _get_code_attribution() -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Extract file path, line number, and function name from the call stack.
    
    Similar to the pattern used in log.py, this finds the first frame that's not
    from the lumberjack SDK to identify where the print statement originated.
    
    Returns:
        Tuple of (filename, line_number, function_name) or (None, None, None) if extraction fails
    """
    try:
        # Walk through the call stack to find the first non-SDK frame
        for frame_info in inspect.stack():
            frame_file = frame_info.filename
            if "lumberjack" not in frame_file and "<frozen" not in frame_file:
                return frame_file, frame_info.lineno, frame_info.function
        # If we couldn't find a non-SDK frame, return None values
        return None, None, None
    except Exception:
        # If extraction fails for any reason, return None values
        return None, None, None


class StdoutWriter:
    """Custom stdout writer that logs messages through Lumberjack."""

    def __init__(self, original_stdout: TextIO):
        """Initialize with the original stdout to forward output.
        
        Args:
            original_stdout: The original stdout to forward output to
        """
        self.original_stdout = original_stdout

    def write(self, text: str) -> int:
        """
        Write text to both the original stdout and log as info.

        Args:
            text: The text to write

        Returns:
            Number of characters written
        """
        # Don't process if we're already inside a write to avoid recursion
        if getattr(_guard, "busy", False):
            return self.original_stdout.write(text)

        _guard.busy = True
        try:
            # Only log non-empty, non-whitespace strings
            if text and not text.isspace():
                # Strip whitespace to clean up the log
                clean_text = text.rstrip()
                if clean_text:
                    # Get the logger directly from OpenTelemetry
                    # This will use our configured LoggerProvider if available
                    otel_logger = logs.get_logger(__name__)
                    if otel_logger:
                        # Extract code attribution for the print statement
                        filename, line_number, function_name = _get_code_attribution()
                        
                        # Build attributes with code attribution
                        attributes: Dict[str, Any] = {SOURCE_KEY_RESERVED_V2: "print"}
                        
                        # Add OpenTelemetry semantic convention attributes
                        if filename:
                            attributes["code.file.path"] = filename
                        if line_number is not None:
                            attributes["code.line.number"] = line_number
                        if function_name:
                            attributes["code.function.name"] = function_name
                        
                        # Create SDK LogRecord with all required fields for OTLP/GRPC exporters
                        now_ns = int(time.time_ns())
                        log_record = SDKLogRecord(
                            timestamp=now_ns,
                            observed_timestamp=now_ns,
                            context=context.get_current(),
                            severity_number=SeverityNumber.INFO,
                            body=clean_text,
                            resource=otel_logger.resource,  # Get resource from logger
                            attributes=attributes
                        )
                        otel_logger.emit(log_record)
        except Exception as e:
            # Ensure we don't break stdout functionality if logging fails
            sdk_logger.error(f"Error in stdout override: {str(e)}")
        finally:
            _guard.busy = False

        # Always write to the original stdout
        return self.original_stdout.write(text)

    def flush(self) -> None:
        """Flush the original stdout."""
        self.original_stdout.flush()
    
    def isatty(self) -> bool:
        """Return whether the original stdout is a TTY."""
        return self.original_stdout.isatty()
    
    def fileno(self) -> int:
        """Return the file descriptor of the original stdout."""
        return self.original_stdout.fileno()
    
    def readable(self) -> bool:
        """Return whether the original stdout is readable."""
        return self.original_stdout.readable()
    
    def writable(self) -> bool:
        """Return whether the original stdout is writable."""
        return self.original_stdout.writable()
    
    def seekable(self) -> bool:
        """Return whether the original stdout is seekable."""
        return self.original_stdout.seekable()
    
    def __getattr__(self, name: str):
        """Delegate any other attribute access to the original stdout."""
        return getattr(self.original_stdout, name)


class StdoutOverride:
    """Class to override stdout and log printed messages through Lumberjack."""

    _original_stdout: Optional[TextIO] = None
    _enabled: bool = False

    @classmethod
    def enable(cls) -> None:
        """Enable stdout override to capture prints as info logs."""
        if not cls._enabled:
            cls._original_stdout = sys.stdout
            sys.stdout = StdoutWriter(cls._original_stdout)
            cls._enabled = True
            sdk_logger.debug("Lumberjack stdout override enabled")

    @classmethod
    def disable(cls) -> None:
        """Disable stdout override and restore original stdout."""
        if cls._enabled and cls._original_stdout is not None:
            sys.stdout = cls._original_stdout
            cls._original_stdout = None
            cls._enabled = False
            sdk_logger.debug("Lumberjack stdout override disabled")

    @classmethod
    def is_enabled(cls) -> bool:
        """Return whether stdout override is enabled."""
        return cls._enabled


# Public API functions
def enable_stdout_override() -> None:
    """
    Enable intercepting of stdout (print statements) and logging them as info logs.
    
    This will capture all print statements and log them as info logs
    while still allowing them to be printed to the original stdout.
    """
    StdoutOverride.enable()


def disable_stdout_override() -> None:
    """
    Disable intercepting of stdout and restore original behavior.
    """
    StdoutOverride.disable()


def is_stdout_override_enabled() -> bool:
    """
    Return whether stdout override is currently enabled.
    
    Returns:
        True if stdout override is enabled, False otherwise
    """
    return StdoutOverride.is_enabled()