"""
Metrics exporter configuration for Lumberjack SDK.
Uses OpenTelemetry's built-in OTLP metrics exporter.
"""

from typing import Optional, Dict, Any
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    PeriodicExportingMetricReader,
    ConsoleMetricExporter
)
from opentelemetry.sdk.resources import Resource

from .internal_utils.fallback_logger import sdk_logger

# Try to import OTLP exporter (may not be installed)
try:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False
    sdk_logger.debug("OTLP metrics exporter not available. Install with: pip install opentelemetry-exporter-otlp-proto-http")


class LumberjackMetricsExporter:
    """Wrapper around OTLP metrics exporter for Lumberjack."""
    
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        project_name: Optional[str] = None,
        config_version: Optional[int] = None,
        update_callback: Optional[Any] = None
    ):
        """Initialize the Lumberjack metrics exporter.
        
        Args:
            api_key: The Lumberjack API key
            endpoint: The metrics endpoint URL
            project_name: Optional project name
            config_version: Optional config version
            update_callback: Optional callback for config updates
        """
        if not OTLP_AVAILABLE:
            raise ImportError(
                "OTLP metrics exporter not available. "
                "Install with: pip install opentelemetry-exporter-otlp-proto-http"
            )
        
        self.api_key = api_key
        self.endpoint = endpoint
        self.project_name = project_name
        self.config_version = config_version
        self.update_callback = update_callback
        
        # Prepare headers for authentication
        headers = {
            "x-api-key": api_key,
            "x-project-name": project_name or "",
        }
        
        if config_version is not None:
            headers["x-config-version"] = str(config_version)
        
        # Create the OTLP metrics exporter
        self.exporter = OTLPMetricExporter(
            endpoint=endpoint,
            headers=headers,
            timeout=30  # 30 second timeout
        )
    
    def get_exporter(self) -> MetricExporter:
        """Get the underlying OTLP exporter.
        
        Returns:
            The OTLPMetricExporter instance
        """
        return self.exporter
    
    def shutdown(self) -> None:
        """Shutdown the exporter."""
        try:
            self.exporter.shutdown()
        except Exception as e:
            sdk_logger.debug(f"Error shutting down metrics exporter: {e}")


def create_metrics_reader(
    exporter: MetricExporter,
    export_interval_millis: int = 60000,  # Default 60 seconds
    export_timeout_millis: int = 30000    # Default 30 seconds
) -> PeriodicExportingMetricReader:
    """Create a periodic exporting metric reader.
    
    Args:
        exporter: The metrics exporter to use
        export_interval_millis: How often to export metrics (in milliseconds)
        export_timeout_millis: Timeout for export operations (in milliseconds)
        
    Returns:
        A PeriodicExportingMetricReader instance
    """
    return PeriodicExportingMetricReader(
        exporter=exporter,
        export_interval_millis=export_interval_millis,
        export_timeout_millis=export_timeout_millis
    )


def create_console_metrics_reader(
    export_interval_millis: int = 60000,
    export_timeout_millis: int = 30000
) -> PeriodicExportingMetricReader:
    """Create a console metrics reader for fallback/debugging.
    
    Args:
        export_interval_millis: How often to export metrics (in milliseconds)
        export_timeout_millis: Timeout for export operations (in milliseconds)
        
    Returns:
        A PeriodicExportingMetricReader instance with ConsoleMetricExporter
    """
    console_exporter = ConsoleMetricExporter()
    return PeriodicExportingMetricReader(
        exporter=console_exporter,
        export_interval_millis=export_interval_millis,
        export_timeout_millis=export_timeout_millis
    )


def create_meter_provider(
    resource: Resource,
    metric_readers: Optional[list] = None
) -> MeterProvider:
    """Create a MeterProvider with the given resource and readers.
    
    Args:
        resource: The resource to associate with metrics
        metric_readers: Optional list of metric readers
        
    Returns:
        A configured MeterProvider instance
    """
    return MeterProvider(
        resource=resource,
        metric_readers=metric_readers or []
    )