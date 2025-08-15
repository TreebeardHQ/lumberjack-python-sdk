"""
Configuration system for Lumberjack SDK.

This module provides typed configuration classes and validation for all SDK settings.
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# Forward declarations for exporters
try:
    from opentelemetry.sdk._logs.export import LogExporter
    from opentelemetry.sdk.trace.export import SpanExporter
    from opentelemetry.sdk.metrics.export import MetricExporter
except ImportError:
    LogExporter = Any  # type: ignore[misc,assignment]
    SpanExporter = Any  # type: ignore[misc,assignment]
    MetricExporter = Any  # type: ignore[misc,assignment]


@dataclass
class LumberjackConfig:
    """
    Typed configuration for Lumberjack SDK.
    
    This class contains all configuration options with proper types,
    defaults, and validation.
    """
    
    # Core settings
    project_name: Optional[str] = None
    api_key: Optional[str] = None
    endpoint: str = "https://api.trylumberjack.com/logs/batch"
    objects_endpoint: Optional[str] = None
    spans_endpoint: Optional[str] = None
    metrics_endpoint: Optional[str] = None
    env: str = "production"
    
    # Batching settings
    batch_size: int = 500
    batch_age: float = 30.0
    flush_interval: float = 30.0
    
    # Output settings
    log_to_stdout: Optional[bool] = None
    stdout_log_level: str = "INFO"
    debug_mode: bool = False
    otel_format: bool = False
    
    # Capture settings
    capture_stdout: Optional[bool] = None
    capture_python_logger: bool = True
    python_logger_level: str = "DEBUG"
    python_logger_name: Optional[str] = None
    
    # Code snippet settings
    code_snippet_enabled: bool = True
    code_snippet_context_lines: int = 5
    code_snippet_max_frames: int = 20
    code_snippet_exclude_patterns: List[str] = field(
        default_factory=lambda: ['site-packages', 'venv', '__pycache__']
    )
    
    # Internal settings
    install_signal_handlers: bool = True
    
    # Local server settings
    local_server_enabled: Optional[bool] = None
    local_server_endpoint: str = "localhost:4317"  # Deprecated: used for fallback only
    local_server_service_name: Optional[str] = None
    
    # Service discovery settings
    service_discovery_enabled: bool = True
    service_discovery_config_path: Optional[str] = None  # Default: ~/.lumberjack.config
    cache_max_size: int = 200
    discovery_interval: float = 30.0
    
    # Custom exporters (for testing and custom integrations)
    custom_log_exporter: Optional[LogExporter] = None
    custom_span_exporter: Optional[SpanExporter] = None
    custom_metrics_exporter: Optional[MetricExporter] = None
    
    def __post_init__(self) -> None:
        """Validate and normalize configuration after initialization."""
        self._apply_environment_variables()
        self._set_defaults()
        self._validate()
    
    def _apply_environment_variables(self) -> None:
        """Apply environment variable overrides."""
        # Core settings
        if self.api_key is None:
            self.api_key = os.getenv('LUMBERJACK_API_KEY')
        if self.project_name is None:
            self.project_name = os.getenv('LUMBERJACK_PROJECT_NAME')
        endpoint_env = os.getenv('LUMBERJACK_ENDPOINT')
        if endpoint_env:
            self.endpoint = endpoint_env
        env_var = os.getenv('LUMBERJACK_ENV')
        if env_var:
            self.env = env_var
        
        # Batching settings
        batch_size_env = os.getenv('LUMBERJACK_BATCH_SIZE')
        if batch_size_env:
            try:
                self.batch_size = int(batch_size_env)
            except ValueError:
                pass
        batch_age_env = os.getenv('LUMBERJACK_BATCH_AGE')
        if batch_age_env:
            try:
                self.batch_age = float(batch_age_env)
            except ValueError:
                pass
        flush_interval_env = os.getenv('LUMBERJACK_FLUSH_INTERVAL')
        if flush_interval_env:
            try:
                self.flush_interval = float(flush_interval_env)
            except ValueError:
                pass
        
        # Output settings
        if self.log_to_stdout is None:
            env_val = os.getenv('LUMBERJACK_LOG_TO_STDOUT')
            if env_val is not None:
                self.log_to_stdout = env_val.lower() in ('true', '1', 'yes', 'on')
        stdout_log_level_env = os.getenv('LUMBERJACK_STDOUT_LOG_LEVEL')
        if stdout_log_level_env:
            self.stdout_log_level = stdout_log_level_env
        debug_mode_env = os.getenv('LUMBERJACK_DEBUG_MODE')
        if debug_mode_env:
            self.debug_mode = debug_mode_env.lower() in ('true', '1', 'yes', 'on')
        otel_format_env = os.getenv('LUMBERJACK_OTEL_FORMAT')
        if otel_format_env:
            self.otel_format = otel_format_env.lower() in ('true', '1', 'yes', 'on')
        
        # Capture settings
        if self.capture_stdout is None:
            env_val = os.getenv('LUMBERJACK_CAPTURE_STDOUT')
            if env_val is not None:
                self.capture_stdout = env_val.lower() in ('true', '1', 'yes', 'on')
        capture_python_logger_env = os.getenv('LUMBERJACK_CAPTURE_PYTHON_LOGGER')
        if capture_python_logger_env:
            self.capture_python_logger = capture_python_logger_env.lower() in (
                'true', '1', 'yes', 'on'
            )
        python_logger_level_env = os.getenv('LUMBERJACK_PYTHON_LOGGER_LEVEL')
        if python_logger_level_env:
            self.python_logger_level = python_logger_level_env
        python_logger_name_env = os.getenv('LUMBERJACK_PYTHON_LOGGER_NAME')
        if python_logger_name_env:
            self.python_logger_name = python_logger_name_env
        
        # Code snippet settings
        code_snippet_enabled_env = os.getenv('LUMBERJACK_CODE_SNIPPET_ENABLED')
        if code_snippet_enabled_env:
            self.code_snippet_enabled = code_snippet_enabled_env.lower() in (
                'true', '1', 'yes', 'on'
            )
        context_lines_env = os.getenv('LUMBERJACK_CODE_SNIPPET_CONTEXT_LINES')
        if context_lines_env:
            try:
                self.code_snippet_context_lines = int(context_lines_env)
            except ValueError:
                pass
        max_frames_env = os.getenv('LUMBERJACK_CODE_SNIPPET_MAX_FRAMES')
        if max_frames_env:
            try:
                self.code_snippet_max_frames = int(max_frames_env)
            except ValueError:
                pass
        if os.getenv('LUMBERJACK_CODE_SNIPPET_EXCLUDE_PATTERNS'):
            patterns = os.getenv('LUMBERJACK_CODE_SNIPPET_EXCLUDE_PATTERNS', '')
            self.code_snippet_exclude_patterns = [
                p.strip() for p in patterns.split(',') if p.strip()
            ]
        
        # Local server settings
        if self.local_server_enabled is None:
            env_val = os.getenv('LUMBERJACK_LOCAL_SERVER_ENABLED')
            if env_val is not None:
                self.local_server_enabled = env_val.lower() in ('true', '1', 'yes', 'on')
        local_server_endpoint_env = os.getenv('LUMBERJACK_LOCAL_SERVER_ENDPOINT')
        if local_server_endpoint_env:
            self.local_server_endpoint = local_server_endpoint_env
        local_server_service_name_env = os.getenv('LUMBERJACK_LOCAL_SERVER_SERVICE_NAME')
        if local_server_service_name_env:
            self.local_server_service_name = local_server_service_name_env
        
        # Service discovery settings
        service_discovery_enabled_env = os.getenv('LUMBERJACK_SERVICE_DISCOVERY_ENABLED')
        if service_discovery_enabled_env:
            self.service_discovery_enabled = service_discovery_enabled_env.lower() in (
                'true', '1', 'yes', 'on'
            )
        service_discovery_config_path_env = os.getenv('LUMBERJACK_SERVICE_DISCOVERY_CONFIG_PATH')
        if service_discovery_config_path_env:
            self.service_discovery_config_path = service_discovery_config_path_env
        cache_max_size_env = os.getenv('LUMBERJACK_CACHE_MAX_SIZE')
        if cache_max_size_env:
            try:
                self.cache_max_size = int(cache_max_size_env)
            except ValueError:
                pass
        discovery_interval_env = os.getenv('LUMBERJACK_DISCOVERY_INTERVAL')
        if discovery_interval_env:
            try:
                self.discovery_interval = float(discovery_interval_env)
            except ValueError:
                pass
    
    def _set_defaults(self) -> None:
        """Set intelligent defaults based on other settings."""
        # Set default endpoints based on main endpoint
        if self.objects_endpoint is None:
            base_url = self.endpoint.replace('/logs/batch', '')
            self.objects_endpoint = f"{base_url}/objects/register"
        
        if self.spans_endpoint is None:
            base_url = self.endpoint.replace('/logs/batch', '')
            self.spans_endpoint = f"{base_url}/spans/batch"
        
        # Set default capture settings based on API key availability
        if self.capture_stdout is None:
            self.capture_stdout = self.api_key is not None
        
        if self.log_to_stdout is None:
            self.log_to_stdout = self.debug_mode or self.api_key is None
        
        # Set default local server settings
        if self.local_server_enabled is None:
            # Enable local server if explicitly requested or in development mode
            self.local_server_enabled = self.debug_mode
        
        # Set service name for local server
        if self.local_server_service_name is None:
            self.local_server_service_name = self.project_name or "default"
    
    def _validate(self) -> None:
        """Validate configuration values."""
        # Validate batch settings
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.batch_age <= 0:
            raise ValueError("batch_age must be positive")
        if self.flush_interval <= 0:
            raise ValueError("flush_interval must be positive")
        
        # Validate log levels
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if self.stdout_log_level.upper() not in valid_levels:
            raise ValueError(f"stdout_log_level must be one of: {', '.join(valid_levels)}")
        if self.python_logger_level.upper() not in valid_levels:
            raise ValueError(f"python_logger_level must be one of: {', '.join(valid_levels)}")
        
        # Validate code snippet settings
        if self.code_snippet_context_lines < 0:
            raise ValueError("code_snippet_context_lines must be non-negative")
        if self.code_snippet_max_frames <= 0:
            raise ValueError("code_snippet_max_frames must be positive")
        
        # Validate service discovery settings
        if self.cache_max_size <= 0:
            raise ValueError("cache_max_size must be positive")
        if self.discovery_interval <= 0:
            raise ValueError("discovery_interval must be positive")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            'project_name': self.project_name,
            'api_key': self.api_key,
            'endpoint': self.endpoint,
            'objects_endpoint': self.objects_endpoint,
            'spans_endpoint': self.spans_endpoint,
            'env': self.env,
            'batch_size': self.batch_size,
            'batch_age': self.batch_age,
            'flush_interval': self.flush_interval,
            'log_to_stdout': self.log_to_stdout,
            'stdout_log_level': self.stdout_log_level,
            'debug_mode': self.debug_mode,
            'otel_format': self.otel_format,
            'capture_stdout': self.capture_stdout,
            'capture_python_logger': self.capture_python_logger,
            'python_logger_level': self.python_logger_level,
            'python_logger_name': self.python_logger_name,
            'code_snippet_enabled': self.code_snippet_enabled,
            'code_snippet_context_lines': self.code_snippet_context_lines,
            'code_snippet_max_frames': self.code_snippet_max_frames,
            'code_snippet_exclude_patterns': self.code_snippet_exclude_patterns,
            'install_signal_handlers': self.install_signal_handlers,
            'local_server_enabled': self.local_server_enabled,
            'local_server_endpoint': self.local_server_endpoint,
            'local_server_service_name': self.local_server_service_name,
            'service_discovery_enabled': self.service_discovery_enabled,
            'service_discovery_config_path': self.service_discovery_config_path,
            'cache_max_size': self.cache_max_size,
            'discovery_interval': self.discovery_interval,
            'custom_log_exporter': self.custom_log_exporter,
            'custom_span_exporter': self.custom_span_exporter,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LumberjackConfig':
        """Create config from dictionary."""
        # Filter out keys that aren't valid for the dataclass
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
    
    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> 'LumberjackConfig':
        """Create config from keyword arguments."""
        return cls.from_dict(kwargs)
    
    def get_logging_level(self, level_str: str) -> int:
        """Convert string log level to logging constant."""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(level_str.upper(), logging.DEBUG)
    
    def is_fallback_mode(self) -> bool:
        """Check if SDK should run in fallback mode (no API key)."""
        return self.api_key is None or self.api_key.strip() == ""
    
    def should_capture_stdout(self) -> bool:
        """Determine if stdout should be captured."""
        return bool(self.capture_stdout)
    
    def should_capture_python_logger(self) -> bool:
        """Determine if Python logger should be captured."""
        return bool(self.capture_python_logger)
    
    def should_log_to_stdout(self) -> bool:
        """Determine if logs should be output to stdout."""
        return bool(self.log_to_stdout)
    
    def should_use_local_server(self) -> bool:
        """Determine if local server should be used for log export."""
        return bool(self.local_server_enabled)
    
    def get_local_server_service_name(self) -> str:
        """Get the service name to use for local server export."""
        return self.local_server_service_name or self.project_name or "default"


# Type aliases for configuration
ConfigDict = Dict[str, Any]
ConfigLike = Union[LumberjackConfig, ConfigDict, None]


def create_config(**kwargs: Any) -> LumberjackConfig:
    """
    Create a LumberjackConfig instance from keyword arguments.
    
    This is a convenience function that can be used as an alternative
    to directly instantiating LumberjackConfig.
    
    Args:
        **kwargs: Configuration options
        
    Returns:
        LumberjackConfig: Configured instance
        
    Example:
        config = create_config(
            api_key="my-key",
            project_name="my-project",
            debug_mode=True
        )
    """
    return LumberjackConfig.from_kwargs(**kwargs)


def load_config_from_env() -> LumberjackConfig:
    """
    Load configuration entirely from environment variables.
    
    Returns:
        LumberjackConfig: Configuration loaded from environment
        
    Example:
        # Set environment variables:
        # LUMBERJACK_API_KEY=my-key
        # LUMBERJACK_PROJECT_NAME=my-project
        # LUMBERJACK_DEBUG_MODE=true
        
        config = load_config_from_env()
    """
    return LumberjackConfig()