"""
OpenTelemetry-based core functionality for the Lumberjack library.

This module provides the same interface as core.py but uses OpenTelemetry
internally for tracing and logging.
"""
import atexit
import os
import signal
import threading
import time
from typing import Any, Dict, Optional, Union

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .version import __version__
from .otel_exporters import LumberjackSpanExporter, LumberjackLogExporter
from .otel_registry import get_global_registry
from .otel_log import initialize_otel_logging
from .internal_utils.fallback_logger import fallback_logger, sdk_logger
from .internal_utils.flush_timer import DEFAULT_FLUSH_INTERVAL, FlushTimerWorker

DEFAULT_API_URL = "https://lumberjack.dev/api/v1/logs/batch"

# Global flag to track if signal handlers are installed
_signal_handlers_installed = False
_original_sigint_handler = None
_original_sigterm_handler = None
_shutdown_lock = threading.Lock()
_is_shutting_down = False


def _handle_shutdown(sig, frame):
    """Handle shutdown signals gracefully."""
    global _is_shutting_down

    with _shutdown_lock:
        if _is_shutting_down:
            # Already shutting down, ignore duplicate signals
            return
        _is_shutting_down = True

    curr_time = round(time.time() * 1000)
    sdk_logger.info(f"Shutdown signal {sig} received, flushing spans and logs...")

    try:
        if OTelLumberjack._instance:
            OTelLumberjack._instance.shutdown()
    except Exception as e:
        sdk_logger.error(f"Error during shutdown: {e}")

    sdk_logger.info(f"Shutdown complete, took {round(time.time() * 1000) - curr_time} ms")


class OTelLumberjack:
    """OpenTelemetry-based Lumberjack core functionality."""
    
    _instance: Optional["OTelLumberjack"] = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the Lumberjack singleton."""
        if hasattr(self, '_init_complete'):
            return
        
        # Initialize instance variables
        self._api_key: Optional[str] = None
        self._endpoint = DEFAULT_API_URL
        self._objects_endpoint = ""
        self._spans_endpoint = ""
        self._project_name: Optional[str] = None
        self._using_fallback = True
        self._config_version: Optional[int] = None
        
        # OTEL providers and exporters
        self._tracer_provider: Optional[TracerProvider] = None
        self._logger_provider: Optional[LoggerProvider] = None
        self._span_exporter: Optional[LumberjackSpanExporter] = None
        self._log_exporter: Optional[LumberjackLogExporter] = None
        self._registry = get_global_registry()
        
        # Configuration
        self._capture_stdout = True
        self._log_to_stdout = False
        self._stdout_log_level = 'INFO'
        self._capture_python_logger = True
        self._python_logger_level = 'DEBUG'
        self._python_logger_name: Optional[str] = None
        self._debug_mode = False
        self._flush_interval = DEFAULT_FLUSH_INTERVAL
        self._code_snippet_enabled = True
        self._code_snippet_context_lines = 5
        self._code_snippet_max_frames = 20
        self._code_snippet_exclude_patterns = ['site-packages', 'venv', '__pycache__']
        
        # Timer
        self._flush_timer: Optional[FlushTimerWorker] = None
        
        self._init_complete = True

    def init(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        project_name: Optional[str] = None,
        batch_size: int = 500,
        batch_age: float = 30.0,
        capture_stdout: Optional[bool] = None,
        log_to_stdout: Optional[bool] = None,
        stdout_log_level: Optional[str] = None,
        capture_python_logger: Optional[bool] = None,
        python_logger_level: Optional[str] = None,
        python_logger_name: Optional[str] = None,
        flush_interval: Optional[float] = None,
        debug_mode: Optional[bool] = None,
        code_snippet_enabled: Optional[bool] = None,
        code_snippet_context_lines: Optional[int] = None,
        code_snippet_max_frames: Optional[int] = None,
        code_snippet_exclude_patterns: Optional[list] = None,
        install_signal_handlers: Optional[bool] = None,
        otel_format: Optional[bool] = None
    ) -> None:
        """Initialize Lumberjack with OpenTelemetry.

        Args:
            api_key: Lumberjack API key
            endpoint: API endpoint URL
            project_name: Name of the project/service
            batch_size: Maximum batch size for logs/spans
            batch_age: Maximum age before flushing batch
            capture_stdout: Whether to capture stdout/print statements
            log_to_stdout: Whether to also log to stdout
            stdout_log_level: Log level for stdout logging
            capture_python_logger: Whether to capture Python logger messages
            python_logger_level: Minimum level for Python logger capture
            python_logger_name: Name of Python logger to capture (None for root)
            flush_interval: Interval for automatic flushing
            debug_mode: Enable debug mode
            code_snippet_enabled: Whether to capture code snippets for errors
            code_snippet_context_lines: Number of context lines around errors
            code_snippet_max_frames: Maximum frames to process for snippets
            code_snippet_exclude_patterns: Patterns to exclude from snippets
            install_signal_handlers: Whether to install signal handlers
            otel_format: Legacy parameter (ignored)
        """
        # Accept some variables even if already initialized
        if project_name is not None:
            self.reset()
            self._project_name = project_name

        if OTelLumberjack._initialized:
            return

        # Set configuration
        self._api_key = api_key if api_key else os.getenv('LUMBERJACK_API_KEY')
        if self._api_key and not isinstance(self._api_key, str):
            raise ValueError("API key must be a string")
        self._api_key = self._api_key.strip() if self._api_key else None

        self._endpoint = endpoint or os.getenv('LUMBERJACK_API_URL', DEFAULT_API_URL)
        self._objects_endpoint = self._endpoint.replace('/logs/batch', '/objects/register')
        self._spans_endpoint = self._endpoint.replace('/logs/batch', '/spans/batch')
        
        self._capture_stdout = capture_stdout if capture_stdout is not None else os.getenv('LUMBERJACK_CAPTURE_STDOUT', True)
        self._log_to_stdout = log_to_stdout if log_to_stdout is not None else os.getenv('LUMBERJACK_LOG_TO_STDOUT', False)
        self._stdout_log_level = stdout_log_level if stdout_log_level is not None else os.getenv('LUMBERJACK_STDOUT_LOG_LEVEL', 'INFO')
        
        self._capture_python_logger = capture_python_logger if capture_python_logger is not None else os.getenv('LUMBERJACK_CAPTURE_PYTHON_LOGGER', True)
        self._python_logger_level = python_logger_level if python_logger_level is not None else os.getenv('LUMBERJACK_PYTHON_LOGGER_LEVEL', 'DEBUG')
        self._python_logger_name = python_logger_name if python_logger_name is not None else os.getenv('LUMBERJACK_PYTHON_LOGGER_NAME', None)
        
        debug_mode_env = os.getenv('LUMBERJACK_DEBUG_MODE')
        self._debug_mode = debug_mode if debug_mode is not None else (debug_mode_env.lower() == 'true' if debug_mode_env else False)
        
        # Set SDK logger level based on debug mode
        if self._debug_mode:
            import logging
            sdk_logger.setLevel(logging.DEBUG)

        self._flush_interval = flush_interval if flush_interval is not None else os.getenv('LUMBERJACK_FLUSH_INTERVAL', DEFAULT_FLUSH_INTERVAL)

        # Initialize code snippet configuration
        self._code_snippet_enabled = code_snippet_enabled if code_snippet_enabled is not None else os.getenv('LUMBERJACK_CODE_SNIPPET_ENABLED', 'true').lower() == 'true'
        self._code_snippet_context_lines = code_snippet_context_lines if code_snippet_context_lines is not None else int(os.getenv('LUMBERJACK_CODE_SNIPPET_CONTEXT_LINES', '5'))
        self._code_snippet_max_frames = code_snippet_max_frames if code_snippet_max_frames is not None else int(os.getenv('LUMBERJACK_CODE_SNIPPET_MAX_FRAMES', '20'))
        exclude_patterns_env = os.getenv('LUMBERJACK_CODE_SNIPPET_EXCLUDE_PATTERNS', 'site-packages,venv,__pycache__')
        self._code_snippet_exclude_patterns = code_snippet_exclude_patterns if code_snippet_exclude_patterns is not None else [p.strip() for p in exclude_patterns_env.split(',') if p.strip()]

        self._using_fallback = not bool(self._api_key)

        # Initialize OpenTelemetry providers and exporters
        self._initialize_otel()

        # Enable stdout capture if requested
        if self._capture_stdout:
            from .otel_log import OTelLog
            OTelLog.enable_stdout_override()
            if self._stdout_log_level:
                fallback_logger.setLevel(self._stdout_log_level)

        # Enable Python logger capture if requested
        if self._capture_python_logger:
            from .otel_log import OTelLog
            import logging
            level_map = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL
            }
            log_level = level_map.get(self._python_logger_level.upper(), logging.DEBUG)
            OTelLog.enable_python_logger_forwarding(level=log_level, logger_name=self._python_logger_name)

        # Install signal handlers
        install_handlers = install_signal_handlers if install_signal_handlers is not None else os.getenv('LUMBERJACK_INSTALL_SIGNAL_HANDLERS', 'true').lower() == 'true'
        if install_handlers:
            self._install_signal_handlers()

        # Start flush timer
        if self._flush_timer is None:
            self._flush_timer = FlushTimerWorker(lumberjack_ref=self, interval=self._flush_interval)
            self._flush_timer.start()

        OTelLumberjack._initialized = True

        if self._api_key:
            sdk_logger.info(f"Lumberjack initialized with OTEL backend: {self.__dict__}")
        else:
            sdk_logger.warning("No API key provided - using fallback logger.")

        sdk_logger.info(f"Lumberjack SDK version: {__version__}")

    def _initialize_otel(self) -> None:
        """Initialize OpenTelemetry providers and exporters."""
        # Create resource
        resource_attributes = {}
        if self._project_name:
            resource_attributes["service.name"] = self._project_name
        resource_attributes["service.version"] = __version__
        resource = Resource.create(resource_attributes)

        # Initialize TracerProvider
        self._tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self._tracer_provider)

        # Initialize LoggerProvider
        self._logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(self._logger_provider)

        if not self._using_fallback:
            # Create custom exporters
            self._span_exporter = LumberjackSpanExporter(
                api_key=self._api_key,
                endpoint=self._spans_endpoint,
                project_name=self._project_name,
                registry=self._registry,
                config_version=self._config_version,
                update_callback=self.update_project_config
            )

            self._log_exporter = LumberjackLogExporter(
                api_key=self._api_key,
                endpoint=self._endpoint,
                project_name=self._project_name,
                config_version=self._config_version,
                update_callback=self.update_project_config
            )

            # Add processors
            span_processor = BatchSpanProcessor(self._span_exporter)
            self._tracer_provider.add_span_processor(span_processor)

            # Initialize OTEL logging
            initialize_otel_logging(self._log_exporter, resource)

    def register_object(self, obj: Any = None, **kwargs: Any) -> None:
        """Register objects for tracking in Lumberjack using the OTEL registry.

        Args:
            obj: Object to register (optional, can be dict or object with attributes)
            **kwargs: Object data to register as keyword arguments. Should include an 'id' field.
        """
        if not self._initialized:
            sdk_logger.warning("Lumberjack is not initialized - object registration will be skipped")
            return

        # Handle single object registration
        if obj is not None:
            formatted_obj = self._format_object(obj)
            if formatted_obj is not None:
                self._registry.attach_to_context(formatted_obj)
            return

        # Handle kwargs registration
        if not kwargs:
            sdk_logger.warning("No object or kwargs provided for registration")
            return

        for key, value in kwargs.items():
            if not isinstance(value, dict):
                # Add the key as an attribute to help with naming
                value._kwarg_key = key

            formatted_obj = self._format_object(value)
            if formatted_obj is not None:
                self._registry.attach_to_context(formatted_obj)

    def _format_object(self, obj_data: Union[Dict[str, Any], Any]) -> Optional[Dict[str, Any]]:
        """Format and validate an object for registration."""
        # Convert object to dict if needed
        if not isinstance(obj_data, dict):
            # Get class name if it's a class instance
            class_name = obj_data.__class__.__name__ if hasattr(obj_data, '__class__') else None

            # Convert object attributes to dict
            try:
                if hasattr(obj_data, '__dict__'):
                    obj_dict = obj_data.__dict__.copy()
                else:
                    # Try to convert using vars()
                    obj_dict = vars(obj_data)
            except TypeError:
                sdk_logger.warning("Cannot convert object to dictionary for registration")
                return None
        else:
            obj_dict = obj_data.copy()
            class_name = None

        # Check for ID field and warn if missing
        if 'id' not in obj_dict:
            sdk_logger.warning("Object registered without 'id' field. This may cause issues with object tracking.")
            return None

        name = None
        if class_name:
            name = class_name.lower()
        if not name and hasattr(obj_data, '_kwarg_key'):
            name = obj_data._kwarg_key.lower()

        obj_id = obj_dict.get('id')

        # Validate and filter fields
        fields = {}
        for key, value in obj_dict.items():
            if key in ['name', 'id']:
                continue

            field_value = self._format_field(key, value)
            if field_value:
                fields[key] = field_value

        return {
            'name': name,
            'id': obj_id,
            'fields': fields
        }

    def _format_field(self, key: str, value: Any) -> Any:
        """Validate if a field should be included in object registration."""
        from datetime import datetime
        
        # Check for numbers
        if isinstance(value, (int, float)):
            return value

        # Check for booleans
        if isinstance(value, bool):
            return value

        # Check for dates
        if isinstance(value, datetime):
            return value.isoformat()

        # Check for searchable strings (under 1024 chars)
        if isinstance(value, str):
            if len(value) <= 1024:
                # Simple heuristic: if it looks like metadata (short, no newlines)
                valid = '\n' not in value and '\r' not in value
                if valid:
                    return value

        return None

    def flush(self) -> int:
        """Force flush all pending data."""
        if not self._initialized:
            return 0

        count = 0
        
        # Force flush OTEL providers
        if self._tracer_provider:
            try:
                self._tracer_provider.force_flush(timeout_millis=5000)
                count += 1
            except Exception as e:
                sdk_logger.error(f"Error flushing traces: {e}")

        if self._logger_provider:
            try:
                self._logger_provider.force_flush(timeout_millis=5000)
                count += 1
            except Exception as e:
                sdk_logger.error(f"Error flushing logs: {e}")

        return count

    def update_project_config(self, config: Dict[str, Any]) -> None:
        """Update project configuration from server response."""
        if 'config_version' in config:
            self._config_version = config['config_version']
            sdk_logger.debug(f"Updated config version to {self._config_version}")

    @property 
    def code_snippet_enabled(self) -> bool:
        """Get code snippet enabled setting."""
        return self._code_snippet_enabled

    @property
    def code_snippet_context_lines(self) -> int:
        """Get code snippet context lines setting."""
        return self._code_snippet_context_lines

    @property
    def code_snippet_max_frames(self) -> int:
        """Get code snippet max frames setting."""
        return self._code_snippet_max_frames

    @property
    def code_snippet_exclude_patterns(self) -> list:
        """Get code snippet exclude patterns."""
        return self._code_snippet_exclude_patterns

    def reset(self) -> None:
        """Reset the Lumberjack instance."""
        OTelLumberjack._initialized = False
        if self._flush_timer:
            self._flush_timer.stop()
            self._flush_timer = None

    def shutdown(self) -> None:
        """Shutdown Lumberjack and flush all data."""
        sdk_logger.info("Shutting down Lumberjack...")
        
        # Flush all data
        self.flush()
        
        # Shutdown OTEL providers
        if self._tracer_provider:
            try:
                self._tracer_provider.shutdown()
            except Exception as e:
                sdk_logger.error(f"Error shutting down tracer provider: {e}")

        if self._logger_provider:
            try:
                self._logger_provider.shutdown()
            except Exception as e:
                sdk_logger.error(f"Error shutting down logger provider: {e}")

        # Stop flush timer
        if self._flush_timer:
            self._flush_timer.stop()
            self._flush_timer = None

        sdk_logger.info("Lumberjack shutdown complete.")

    def _install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""
        global _signal_handlers_installed, _original_sigint_handler, _original_sigterm_handler

        if _signal_handlers_installed:
            return

        try:
            _original_sigint_handler = signal.signal(signal.SIGINT, _handle_shutdown)
            _original_sigterm_handler = signal.signal(signal.SIGTERM, _handle_shutdown)
            _signal_handlers_installed = True
            atexit.register(self.shutdown)
            sdk_logger.debug("Signal handlers installed for graceful shutdown")
        except Exception as e:
            sdk_logger.warning(f"Could not install signal handlers: {e}")

    # Class methods for backward compatibility
    @classmethod
    def register(cls, obj: Any = None, **kwargs: Any) -> None:
        """Register objects for tracking in Lumberjack."""
        instance = cls()
        instance.register_object(obj, **kwargs)


# Backward compatibility alias
Lumberjack = OTelLumberjack