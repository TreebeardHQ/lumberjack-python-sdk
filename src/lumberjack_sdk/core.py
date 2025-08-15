"""
Core functionality for the lumberjack library.
"""

import atexit
import logging
import signal
import sys
import threading
import time
import types
from typing import Any, Dict, List, Optional

from opentelemetry import _logs as logs  # type: ignore[attr-defined]
from opentelemetry import trace
from opentelemetry import metrics
from opentelemetry._logs import Logger   # type: ignore[attr-defined]
from opentelemetry.sdk._logs import LoggerProvider  # type: ignore[attr-defined]
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, SimpleLogRecordProcessor  # type: ignore[attr-defined]
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader




from lumberjack_sdk.internal_utils.flush_timer import  FlushTimerWorker

from .config import LumberjackConfig
from .exception_handlers import ExceptionHandlers
from .logging_instrumentation import enable_python_logger_forwarding
from .object_registration import ObjectRegistration
from .stdout_override import enable_stdout_override

# LoggingContext removed - using OpenTelemetry context directly
from .exporters import LumberjackLogExporter, LumberjackSpanExporter
from .fallback_exporters import FallbackLogExporter
from .internal_utils.fallback_logger import fallback_logger, sdk_logger
from .version import __version__

# SpanContext now comes directly from OpenTelemetry

has_warned = False


# Global flag to track if signal handlers are installed
_signal_handlers_installed = False
_original_sigint_handler = None
_original_sigterm_handler = None
_shutdown_lock = threading.Lock()
_is_shutting_down = False


def _handle_shutdown(sig: int, frame: Optional[types.FrameType]) -> None:
    """Handle shutdown signals gracefully."""
    global _is_shutting_down

    with _shutdown_lock:
        if _is_shutting_down:
            # Already shutting down, ignore duplicate signals
            return
        _is_shutting_down = True

    curr_time = round(time.time() * 1000)
    sdk_logger.info(
        f"Shutdown signal {sig} received, flushing logs, objects, and spans...")

    try:
        instance = Lumberjack.get_instance()
        if instance:
            instance.shutdown()
    except Exception as e:
        sdk_logger.error(f"Error during shutdown: {e}")

    sdk_logger.info(
        f"Shutdown complete, took {round(time.time() * 1000) - curr_time} ms")

    # Call original handlers if they exist
    if sig == signal.SIGINT and _original_sigint_handler:
        if callable(_original_sigint_handler):
            _original_sigint_handler(sig, frame)
    elif sig == signal.SIGTERM and _original_sigterm_handler:
        if callable(_original_sigterm_handler):
            _original_sigterm_handler(sig, frame)
    else:
        # Default behavior - exit
        sys.exit(0)


# Constants
DEFAULT_BATCH_SIZE = 500
DEFAULT_BATCH_AGE = 30.0
DEFAULT_API_URL = 'https://api.trylumberjack.com/logs/batch'



class Lumberjack:
    _instance: Optional['Lumberjack'] = None
    _initialized = False
    _config: Optional[LumberjackConfig] = None
    
    # Runtime state
    _object_registration: Optional[ObjectRegistration] = None
    _flush_timer: Optional[FlushTimerWorker] = None
    _tracer_provider: Optional[TracerProvider] = None
    _logger_provider: Optional[LoggerProvider] = None
    _meter_provider: Optional[MeterProvider] = None
    _logger: Optional[Logger] = None
    _log_processor: Optional[BatchLogRecordProcessor] = None
    _local_server_processor: Optional[BatchLogRecordProcessor] = None
    _metrics_reader: Optional[PeriodicExportingMetricReader] = None
    _is_shutdown: bool = False

    _config_version: Optional[int] = None

    _initialized = False

    def __new__(cls, *args: Any, **kwargs: Any) -> 'Lumberjack':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        # Core settings
        project_name: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        objects_endpoint: Optional[str] = None,
        spans_endpoint: Optional[str] = None,
        metrics_endpoint: Optional[str] = None,
        env: Optional[str] = None,
        
        # Batching settings
        batch_size: Optional[int] = None,
        batch_age: Optional[float] = None,
        flush_interval: Optional[float] = None,
        
        # Output settings
        log_to_stdout: Optional[bool] = None,
        stdout_log_level: Optional[str] = None,
        debug_mode: Optional[bool] = None,
        otel_format: Optional[bool] = None,
        
        # Capture settings
        capture_stdout: Optional[bool] = None,
        capture_python_logger: Optional[bool] = None,
        python_logger_level: Optional[str] = None,
        python_logger_name: Optional[str] = None,
        
        # Code snippet settings
        code_snippet_enabled: Optional[bool] = None,
        code_snippet_context_lines: Optional[int] = None,
        code_snippet_max_frames: Optional[int] = None,
        code_snippet_exclude_patterns: Optional[List[str]] = None,
        
        # Internal settings
        install_signal_handlers: Optional[bool] = None,
        
        # Local server settings
        local_server_enabled: Optional[bool] = None,
        local_server_endpoint: Optional[str] = None,
        local_server_service_name: Optional[str] = None,
        
        # Custom exporters (for testing and custom integrations)
        custom_log_exporter: Optional[Any] = None,
        custom_span_exporter: Optional[Any] = None,
        custom_metrics_exporter: Optional[Any] = None,
    ):
        """
        Initialize the Lumberjack class.

        All configuration options can be passed as keyword arguments.
        See LumberjackConfig for full documentation of available options.
        """
        # Handle reinitialization logic
        if project_name is not None and Lumberjack._initialized:
            self.reset()
        
        if Lumberjack._initialized:
            return
        
        # Create configuration from all provided arguments
        config_kwargs = {
            k: v for k, v in locals().items() 
            if k not in ('self',) and v is not None
        }
        self._config = LumberjackConfig(**config_kwargs)

        # Set SDK logger level based on debug mode
        if self._config.debug_mode:
            sdk_logger.setLevel(logging.DEBUG)
        else:
            sdk_logger.setLevel(logging.INFO)

        # Register exception handlers
        ExceptionHandlers.register()

        Lumberjack._initialized = True

        self._using_fallback = self._config.is_fallback_mode()

        if self._flush_timer is None:
            self._flush_timer = FlushTimerWorker(
                flush_callback=self.flush_objects, interval=self._config.flush_interval)
            self._flush_timer.start()

        # Initialize OpenTelemetry providers
        if not self._config.is_fallback_mode():
            self._initialize_otel_providers(batch_size=self._config.batch_size, batch_age=self._config.batch_age)
        else:
            # Initialize basic OpenTelemetry providers with console exporter for fallback mode
            self._initialize_fallback_otel_providers()

        # Enable stdout capture if requested
        # This is done after OTel providers are initialized so logger is available
        if self._config.should_capture_stdout():
            enable_stdout_override()
            if self._config.stdout_log_level:
                fallback_logger.setLevel(self._config.stdout_log_level)

        # Enable Python logger capture if requested
        if self._config.should_capture_python_logger():
            log_level = self._config.get_logging_level(self._config.python_logger_level)
            enable_python_logger_forwarding(
                level=log_level, logger_name=self._config.python_logger_name)
        
        # Initialize object registration (handles its own exporter and batching)
        self._object_registration = ObjectRegistration(config=self._config)

        if not self._config.is_fallback_mode():
            sdk_logger.info(
                f"Lumberjack initialized with config: {self._config.to_dict()}")
        else:
            sdk_logger.warning(
                "No API key provided - using fallback logger.")

        # Print SDK version for debugging
        sdk_logger.info(f"Lumberjack SDK version: {__version__}")

        # Install signal handlers if requested (handled by config)
        self._install_signal_handlers = self._config.install_signal_handlers

        if self._install_signal_handlers:
            self._setup_signal_handlers()

        # Register atexit handler as a fallback
        atexit.register(self._atexit_handler)

    def _setup_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""
        global _signal_handlers_installed, _original_sigint_handler, _original_sigterm_handler

        if not _signal_handlers_installed:
            # Save original handlers
            _original_sigint_handler = signal.signal(
                signal.SIGINT, _handle_shutdown)
            _original_sigterm_handler = signal.signal(
                signal.SIGTERM, _handle_shutdown)
            _signal_handlers_installed = True
            sdk_logger.debug("Signal handlers installed for graceful shutdown")

    def _atexit_handler(self) -> None:
        """Handle cleanup at exit time."""
        global _is_shutting_down

        with _shutdown_lock:
            if _is_shutting_down:
                return
            _is_shutting_down = True

        try:
            # During interpreter shutdown, avoid operations that might try to create threads
            import sys
            if hasattr(sys, '_getframe'):  # Check if interpreter is still fully operational
                self.shutdown()
        except Exception as _e:
            # Ignore errors during shutdown - interpreter might be in shutdown state
            pass

    def _initialize_otel_providers(self, batch_size: int, batch_age: float) -> None:
        """Initialize OpenTelemetry providers with Lumberjack exporters."""
        if not self._config:
            raise RuntimeError("Config must be initialized before OTel providers")
            
        # Create resource
        resource_attributes: Dict[str, Any] = {"service.name": self._project_name} if self._project_name else {}
        resource = Resource.create(resource_attributes)

        # Initialize TracerProvider
        self._tracer_provider = TracerProvider(resource=resource)
        
        # Create and add span exporter (use custom if provided)
        if self._config.custom_span_exporter:
            self._span_exporter = self._config.custom_span_exporter
        else:
            self._span_exporter = LumberjackSpanExporter(
                api_key=self._config.api_key or "",
                endpoint=self._config.spans_endpoint or "",
                project_name=self._config.project_name,
                config_version=self._config_version,
                update_callback=self.update_project_config
            )
        
        span_processor = BatchSpanProcessor(
            self._span_exporter,
            max_queue_size=batch_size * 2,
            max_export_batch_size=batch_size,
            export_timeout_millis=int(batch_age * 1000)
        )
        self._tracer_provider.add_span_processor(span_processor)
        
        # Set as global provider
        trace.set_tracer_provider(self._tracer_provider)
        
        # Initialize MeterProvider
        try:
            from .metrics_exporter import LumberjackMetricsExporter, create_metrics_reader
        except ImportError:
            sdk_logger.debug("Metrics exporter not available")
            LumberjackMetricsExporter = None
            create_metrics_reader = None
        
        # Create and add metrics exporter (use custom if provided)
        self._metrics_exporter = None  # Initialize the attribute
        self._metrics_reader = None   # Initialize the attribute
        
        if self._config.custom_metrics_exporter:
            self._metrics_exporter = self._config.custom_metrics_exporter
        else:
            # Only create metrics exporter if metrics_endpoint is configured and available
            if self._config.metrics_endpoint and LumberjackMetricsExporter:
                try:
                    metrics_exporter_wrapper = LumberjackMetricsExporter(
                        api_key=self._config.api_key or "",
                        endpoint=self._config.metrics_endpoint,
                        project_name=self._config.project_name,
                        config_version=self._config_version,
                        update_callback=self.update_project_config
                    )
                    self._metrics_exporter = metrics_exporter_wrapper.get_exporter()
                except Exception as e:
                    sdk_logger.warning(f"Failed to create metrics exporter: {e}")
                    self._metrics_exporter = None
        
        # Create metric readers list
        metric_readers = []
        if self._metrics_exporter and create_metrics_reader:
            self._metrics_reader = create_metrics_reader(
                self._metrics_exporter,
                export_interval_millis=30000,  # Export every 30 seconds (faster for development)
                export_timeout_millis=10000    # 10 second timeout
            )
            metric_readers.append(self._metrics_reader)
        
        # Create MeterProvider with readers
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=metric_readers
        )
        
        # Set as global provider
        metrics.set_meter_provider(self._meter_provider)

        # Initialize LoggerProvider
        self._logger_provider = LoggerProvider(resource=resource)
        
        # Create and add log exporter (use custom if provided)
        if self._config.custom_log_exporter:
            self._log_exporter = self._config.custom_log_exporter
        else:
            self._log_exporter = LumberjackLogExporter(
                api_key=self._config.api_key or "",
                endpoint=self._config.endpoint or "",
                project_name=self._config.project_name,
                config_version=self._config_version,
                update_callback=self.update_project_config
            )
        
        self._log_processor = BatchLogRecordProcessor(
            self._log_exporter,
            max_queue_size=batch_size * 2,
            max_export_batch_size=batch_size,
            export_timeout_millis=int(batch_age * 1000)
        )
        self._logger_provider.add_log_record_processor(self._log_processor)
        
        # Add local server exporter if enabled
        self._local_server_processor = None
        if self._config.should_use_local_server():
            try:
                from .local_server.local_exporter import create_local_server_exporter
                
                # Create exporter with service discovery (no endpoint needed)
                local_exporter = create_local_server_exporter(
                    service_name=self._config.get_local_server_service_name(),
                    cache_max_size=self._config.cache_max_size,
                    discovery_interval=self._config.discovery_interval
                )
                
                # Use SimpleLogRecordProcessor for immediate delivery in local development
                self._local_server_processor = SimpleLogRecordProcessor(local_exporter)
                self._logger_provider.add_log_record_processor(self._local_server_processor)
                sdk_logger.info(f"Local server exporter enabled with service discovery for service: {self._config.get_local_server_service_name()}")
                    
            except ImportError:
                sdk_logger.debug("Local server dependencies not installed. Install with: pip install 'lumberjack_sdk[local-server]'")
            except Exception as e:
                sdk_logger.warning(f"Failed to initialize local server exporter: {e}")
        
        # Set as global provider
        logs.set_logger_provider(self._logger_provider)  # type: ignore[attr-defined]
        self._logger = logs.get_logger(__name__, __version__)  # type: ignore[attr-defined]
        
        sdk_logger.info("OpenTelemetry providers initialized")

    def _initialize_fallback_otel_providers(self) -> None:
        """Initialize basic OpenTelemetry providers with console exporters for fallback mode."""
        if not self._config:
            raise RuntimeError("Config must be initialized before OTel providers")
        
        # Create resource
        resource_attributes: Dict[str, Any] = {"service.name": self._project_name} if self._project_name else {}
        resource = Resource.create(resource_attributes)

        # Initialize TracerProvider without any exporters (no span output in fallback mode)
        self._tracer_provider = TracerProvider(resource=resource)
        
        # Set as global provider (but don't add any processors - no span output)
        trace.set_tracer_provider(self._tracer_provider)
        
        # Initialize MeterProvider - check for custom exporter even in fallback mode
        try:
            from .metrics_exporter import create_metrics_reader
        except ImportError:
            create_metrics_reader = None
        
        # Create and add metrics exporter (use custom if provided)
        self._metrics_exporter = None  # Initialize the attribute
        self._metrics_reader = None   # Initialize the attribute
        metric_readers = []
        
        if self._config.custom_metrics_exporter and create_metrics_reader:
            self._metrics_exporter = self._config.custom_metrics_exporter
            self._metrics_reader = create_metrics_reader(
                self._metrics_exporter,
                export_interval_millis=30000,  # Consistent with normal mode
                export_timeout_millis=10000
            )
            metric_readers.append(self._metrics_reader)
        
        # Create MeterProvider with readers (empty list if no custom exporter)
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=metric_readers
        )
        
        # Set as global provider
        metrics.set_meter_provider(self._meter_provider)

        # Initialize LoggerProvider with fallback exporter
        self._logger_provider = LoggerProvider(resource=resource)
        
        fallback_log_exporter = FallbackLogExporter()
        # Use SimpleLogRecordProcessor for fallback to avoid thread issues during shutdown
        self._log_processor = SimpleLogRecordProcessor(fallback_log_exporter)
        self._logger_provider.add_log_record_processor(self._log_processor)
        
        # Add local server exporter even in fallback mode if enabled
        self._local_server_processor = None
        if self._config.should_use_local_server():
            try:
                from .local_server.local_exporter import create_local_server_exporter
                
                # Create exporter with service discovery (no endpoint needed)
                local_exporter = create_local_server_exporter(
                    service_name=self._config.get_local_server_service_name(),
                    cache_max_size=self._config.cache_max_size,
                    discovery_interval=self._config.discovery_interval
                )
                
                # Use SimpleLogRecordProcessor in fallback mode as well
                self._local_server_processor = SimpleLogRecordProcessor(local_exporter)
                self._logger_provider.add_log_record_processor(self._local_server_processor)
                sdk_logger.info(f"Local server exporter enabled in fallback mode with service discovery for service: {self._config.get_local_server_service_name()}")
                    
            except ImportError:
                sdk_logger.debug("Local server dependencies not installed. Install with: pip install 'lumberjack_sdk[local-server]'")
            except Exception as e:
                sdk_logger.warning(f"Failed to initialize local server exporter in fallback mode: {e}")
        
        # Set as global provider
        logs.set_logger_provider(self._logger_provider)  # type: ignore[attr-defined]
        self._logger = logs.get_logger(__name__, __version__)  # type: ignore[attr-defined]
        
        sdk_logger.info("OpenTelemetry providers initialized in fallback mode with console exporters")

    def shutdown(self) -> None:
        """
        Perform graceful shutdown of the SDK.

        This method:
        - Flushes pending objects through OpenTelemetry providers
        - Stops the flush timer
        - Stops the exporter worker thread
        - Cleans up resources

        Call this method when your application is shutting down to ensure
        all data is sent to Lumberjack.
        """
        if not self._initialized or self._is_shutdown:
            return

        self._is_shutdown = True

        try:
            # Flush pending objects
            if self._object_registration:
                self._object_registration.flush_objects()
            
            # Shutdown OpenTelemetry providers (be resilient to shutdown errors)
            try:
                if hasattr(self, '_tracer_provider') and self._tracer_provider:
                    self._tracer_provider.shutdown()
            except Exception:
                pass  # Ignore errors during shutdown
            
            try:
                if hasattr(self, '_logger_provider') and self._logger_provider:
                    self._logger_provider.shutdown()
            except Exception:
                pass  # Ignore errors during shutdown
            
            try:
                if hasattr(self, '_meter_provider') and self._meter_provider:
                    self._meter_provider.shutdown()
            except Exception:
                pass  # Ignore errors during shutdown

            # Stop the flush timer
            if self._flush_timer:
                self._flush_timer.stop()
                self._flush_timer.join(timeout=5)
                self._flush_timer = None

            # Shutdown Python logger forwarding to prevent threading issues
            try:
                from .logging_instrumentation import disable_python_logger_forwarding
                disable_python_logger_forwarding()
            except Exception:
                pass

            # Shutdown object registration (handles its own exporter)
            if self._object_registration:
                self._object_registration.shutdown()
                self._object_registration = None

            sdk_logger.info("Lumberjack SDK shutdown complete")
        except Exception as e:
            sdk_logger.error(f"Error during shutdown: {e}")

    @classmethod
    def init(cls, **kwargs: Any) -> None:
        """
        Initialize the Lumberjack class.

        @see Lumberjack.__init__
        """
        cls(**kwargs)  # Triggers __new__ and __init__

    @classmethod
    def get_instance(cls) -> Optional['Lumberjack']:
        """Get the current Lumberjack instance if it exists."""
        return cls._instance

    def update_project_config(self, config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """
        Update the project config by merging incoming changes with existing config.

        Args:
            config: Optional configuration dictionary (for backward compatibility)
            **kwargs: Configuration options as keyword arguments
        """
        if not self._config:
            sdk_logger.warning("No existing config to update")
            return
            
        # Merge config dict if provided (for backward compatibility)
        update_data: Dict[str, Any] = {}
        if config is not None:
            update_data.update(config)
        
        # Add kwargs to update data
        update_data.update(kwargs)
        
        if not update_data:
            return  # Nothing to update
        
        # Handle config_version separately as it's not part of LumberjackConfig
        if 'config_version' in update_data:
            self._config_version = update_data.pop('config_version')
        
        # Create new config by merging existing config with updates
        current_config_dict = self._config.to_dict()
        current_config_dict.update(update_data)
        
        # Create new config object
        try:
            new_config = LumberjackConfig.from_dict(current_config_dict)
            old_config = self._config
            self._config = new_config
            
            # Apply configuration changes that require immediate action
            self._apply_config_changes(old_config, new_config)
            
            sdk_logger.debug(f"Config updated with: {update_data}")
            
        except Exception as e:
            sdk_logger.error(f"Failed to update config: {e}")
    
    def _apply_config_changes(self, old_config: LumberjackConfig, new_config: LumberjackConfig) -> None:
        """Apply configuration changes that require immediate action.
        
        Args:
            old_config: Previous configuration
            new_config: New configuration
        """
        # Update SDK logger level if debug mode changed
        if old_config.debug_mode != new_config.debug_mode:
            if new_config.debug_mode:
                sdk_logger.setLevel(logging.DEBUG)
            else:
                sdk_logger.setLevel(logging.INFO)
        
        # Update fallback logger level if stdout log level changed
        if old_config.stdout_log_level != new_config.stdout_log_level:
            fallback_logger.setLevel(new_config.stdout_log_level)
        
        # Enable/disable stdout capture if setting changed
        if old_config.should_capture_stdout() != new_config.should_capture_stdout():
            if new_config.should_capture_stdout():
                enable_stdout_override()
            # Note: We don't disable stdout override as it may break existing capture
        
        # Update Python logger forwarding if settings changed
        if (old_config.should_capture_python_logger() != new_config.should_capture_python_logger() or
            old_config.python_logger_level != new_config.python_logger_level or
            old_config.python_logger_name != new_config.python_logger_name):
            
            if new_config.should_capture_python_logger():
                log_level = new_config.get_logging_level(new_config.python_logger_level)
                enable_python_logger_forwarding(
                    level=log_level, 
                    logger_name=new_config.python_logger_name
                )
        
        # Update object registration config if it exists
        if self._object_registration:
            self._object_registration.update_config(new_config)

    @property
    def config(self) -> Optional[LumberjackConfig]:
        """Get the current configuration."""
        return self._config
    
    @property
    def api_key(self) -> Optional[str]:
        return self._config.api_key if self._config else None

    @property
    def debug_mode(self) -> bool:
        return self._config.debug_mode if self._config else False

    @property
    def code_snippet_enabled(self) -> bool:
        return self._config.code_snippet_enabled if self._config else True

    @property
    def code_snippet_context_lines(self) -> int:
        return self._config.code_snippet_context_lines if self._config else 5

    @property
    def code_snippet_max_frames(self) -> int:
        return self._config.code_snippet_max_frames if self._config else 20

    @property
    def code_snippet_exclude_patterns(self) -> List[str]:
        return self._config.code_snippet_exclude_patterns if self._config else ['site-packages', 'venv', '__pycache__']
    
    @property
    def log_processor(self) -> Optional[BatchLogRecordProcessor]:
        """Get the current log processor for testing."""
        return self._log_processor
    
    # Legacy compatibility properties
    @property
    def _api_key(self) -> Optional[str]:
        return self._config.api_key if self._config else None
        
    @property
    def _endpoint(self) -> str:
        return self._config.endpoint if self._config else "https://api.trylumberjack.com/logs/batch"
        
    @property
    def _env(self) -> str:
        return self._config.env if self._config else "production"
        
    @property
    def _log_to_stdout(self) -> bool:
        return self._config.should_log_to_stdout() if self._config else False
        
    @property
    def _project_name(self) -> Optional[str]:
        return self._config.project_name if self._config else None

    @classmethod
    def reset(cls) -> None:
        """Reset the Lumberjack singleton instance."""
        global has_warned

        has_warned = False
        if cls._instance:
            # Clear runtime state
            cls._instance._config = None
            cls._instance._using_fallback = True
            cls._instance._is_shutdown = False
            
            # Stop flush timer if running
            if cls._instance._flush_timer:
                cls._instance._flush_timer.stop()
                cls._instance._flush_timer = None
            
            # Shutdown object registration
            if cls._instance._object_registration:
                cls._instance._object_registration.shutdown()
                cls._instance._object_registration = None
                
            # Reset SDK logger level
            sdk_logger.setLevel(logging.INFO)
            
            cls._initialized = False



    def register_object(self, obj: Any = None, **kwargs: Any) -> None:
        """Register objects for tracking in Lumberjack.

        Args:
            obj: Object to register (optional, can be dict or object with attributes)
            **kwargs: Object data to register as keyword arguments. Should include an 'id' field.
        """
        if not self._initialized:
            sdk_logger.warning(
                "Lumberjack is not initialized - object registration will be skipped")
            return

        if self._object_registration:
            self._object_registration.register_object(obj, **kwargs)

    def flush_objects(self) -> int:
        """Flush all pending object registrations.

        Returns:
            Number of objects flushed
        """
        if not self._initialized:
            raise RuntimeError(
                "Lumberjack must be initialized before flushing objects")

        if self._object_registration:
            return self._object_registration.flush_objects()
        return 0

   


    @classmethod
    def register(cls, obj: Any = None, **kwargs: Any) -> None:
        """Register objects for tracking in Lumberjack (class method).

        Args:
            obj: Object to register (optional, can be dict or object with attributes)
            **kwargs: Object data to register as keyword arguments. Should include an 'id' field.
        """
        instance = cls()
        instance.register_object(obj, **kwargs)


    @property
    def tracer(self) -> Optional[trace.Tracer]:
        """Get the OpenTelemetry tracer instance."""
        return trace.get_tracer(__name__, __version__) if self._tracer_provider else None

    @property
    def logger(self) -> Optional[Logger]:
        """Get the OpenTelemetry logger instance."""
        return self._logger
    
    @property
    def meter(self) -> Optional[metrics.Meter]:
        """Get the OpenTelemetry meter instance."""
        return metrics.get_meter(__name__, __version__) if self._meter_provider else None
