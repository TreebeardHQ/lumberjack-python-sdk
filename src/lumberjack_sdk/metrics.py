"""
Metrics functionality for the Lumberjack SDK.
Provides OpenTelemetry metrics APIs and helpers like RED metrics.
"""

from typing import Any, Dict, Optional, Callable
from contextlib import contextmanager
import time

from opentelemetry import metrics
from opentelemetry.metrics import (
    Counter,
    Histogram,
    UpDownCounter,
    ObservableCounter,
    ObservableGauge,
    ObservableUpDownCounter,
    Meter,
    CallbackOptions,
    Observation
)


class MetricsAPI:
    """Wrapper around OpenTelemetry metrics API for Lumberjack."""
    
    _instance: Optional['MetricsAPI'] = None
    _meter: Optional[Meter] = None
    
    def __new__(cls) -> 'MetricsAPI':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the metrics API."""
        if self._meter is None:
            # Get the meter from the global meter provider
            from .version import __version__
            self._meter = metrics.get_meter("lumberjack-sdk", __version__)
    
    @property
    def meter(self) -> Meter:
        """Get the OpenTelemetry meter instance."""
        if self._meter is None:
            from .version import __version__
            self._meter = metrics.get_meter("lumberjack-sdk", __version__)
        return self._meter
    
    def create_counter(
        self,
        name: str,
        unit: str = "",
        description: str = ""
    ) -> Counter:
        """Create a counter metric.
        
        Args:
            name: The name of the metric
            unit: The unit of measurement (e.g., "1", "bytes", "ms")
            description: A description of what this metric measures
            
        Returns:
            A Counter instance
        """
        return self.meter.create_counter(
            name=name,
            unit=unit,
            description=description
        )
    
    def create_histogram(
        self,
        name: str,
        unit: str = "",
        description: str = ""
    ) -> Histogram:
        """Create a histogram metric.
        
        Args:
            name: The name of the metric
            unit: The unit of measurement (e.g., "ms", "bytes")
            description: A description of what this metric measures
            
        Returns:
            A Histogram instance
        """
        return self.meter.create_histogram(
            name=name,
            unit=unit,
            description=description
        )
    
    def create_up_down_counter(
        self,
        name: str,
        unit: str = "",
        description: str = ""
    ) -> UpDownCounter:
        """Create an up-down counter metric.
        
        Args:
            name: The name of the metric
            unit: The unit of measurement
            description: A description of what this metric measures
            
        Returns:
            An UpDownCounter instance
        """
        return self.meter.create_up_down_counter(
            name=name,
            unit=unit,
            description=description
        )
    
    def create_observable_counter(
        self,
        name: str,
        callbacks: list[Callable[[CallbackOptions], list[Observation]]],
        unit: str = "",
        description: str = ""
    ) -> ObservableCounter:
        """Create an observable counter metric.
        
        Args:
            name: The name of the metric
            callbacks: List of callback functions that return observations
            unit: The unit of measurement
            description: A description of what this metric measures
            
        Returns:
            An ObservableCounter instance
        """
        return self.meter.create_observable_counter(
            name=name,
            callbacks=callbacks,
            unit=unit,
            description=description
        )
    
    def create_observable_gauge(
        self,
        name: str,
        callbacks: list[Callable[[CallbackOptions], list[Observation]]],
        unit: str = "",
        description: str = ""
    ) -> ObservableGauge:
        """Create an observable gauge metric.
        
        Args:
            name: The name of the metric
            callbacks: List of callback functions that return observations
            unit: The unit of measurement
            description: A description of what this metric measures
            
        Returns:
            An ObservableGauge instance
        """
        return self.meter.create_observable_gauge(
            name=name,
            callbacks=callbacks,
            unit=unit,
            description=description
        )
    
    def create_observable_up_down_counter(
        self,
        name: str,
        callbacks: list[Callable[[CallbackOptions], list[Observation]]],
        unit: str = "",
        description: str = ""
    ) -> ObservableUpDownCounter:
        """Create an observable up-down counter metric.
        
        Args:
            name: The name of the metric
            callbacks: List of callback functions that return observations
            unit: The unit of measurement
            description: A description of what this metric measures
            
        Returns:
            An ObservableUpDownCounter instance
        """
        return self.meter.create_observable_up_down_counter(
            name=name,
            callbacks=callbacks,
            unit=unit,
            description=description
        )


class REDMetrics:
    """Helper class for RED (Rate, Errors, Duration) metrics pattern.
    
    RED metrics are a popular pattern for monitoring services:
    - Rate: The number of requests per second
    - Errors: The number of failed requests
    - Duration: The time each request takes
    """
    
    def __init__(
        self,
        service_name: str,
        metrics_api: Optional[MetricsAPI] = None
    ):
        """Initialize RED metrics for a service.
        
        Args:
            service_name: The name of the service being monitored
            metrics_api: Optional MetricsAPI instance (creates one if not provided)
        """
        self.service_name = service_name
        self.metrics_api = metrics_api or MetricsAPI()
        
        # Create the three RED metrics
        self.request_counter = self.metrics_api.create_counter(
            name=f"{service_name}_requests_total",
            unit="1",
            description=f"Total number of requests for {service_name}"
        )
        
        self.error_counter = self.metrics_api.create_counter(
            name=f"{service_name}_errors_total",
            unit="1",
            description=f"Total number of errors for {service_name}"
        )
        
        self.duration_histogram = self.metrics_api.create_histogram(
            name=f"{service_name}_request_duration_seconds",
            unit="s",
            description=f"Request duration in seconds for {service_name}"
        )
    
    def record_request(
        self,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a request.
        
        Args:
            attributes: Optional attributes to attach to the metric
        """
        self.request_counter.add(1, attributes=attributes)
    
    def record_error(
        self,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an error.
        
        Args:
            attributes: Optional attributes to attach to the metric
        """
        self.error_counter.add(1, attributes=attributes)
    
    def record_duration(
        self,
        duration_seconds: float,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a request duration.
        
        Args:
            duration_seconds: The duration in seconds
            attributes: Optional attributes to attach to the metric
        """
        self.duration_histogram.record(duration_seconds, attributes=attributes)
    
    @contextmanager
    def measure(
        self,
        operation: str = "request",
        record_errors: bool = True,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Context manager to measure a request/operation.
        
        This automatically records the request, duration, and optionally errors.
        
        Args:
            operation: The name of the operation (added to attributes)
            record_errors: Whether to record exceptions as errors
            attributes: Optional attributes to attach to metrics
            
        Example:
            ```python
            red_metrics = REDMetrics("my_service")
            
            with red_metrics.measure(operation="fetch_user", attributes={"user_id": "123"}):
                # Your code here
                user = fetch_user_from_db("123")
            ```
        """
        # Prepare attributes
        attrs = attributes or {}
        attrs["operation"] = operation
        
        # Record the request
        self.record_request(attributes=attrs)
        
        # Start timing
        start_time = time.perf_counter()
        
        try:
            yield
        except Exception as e:
            # Record error if configured
            if record_errors:
                error_attrs = attrs.copy()
                error_attrs["error_type"] = type(e).__name__
                self.record_error(attributes=error_attrs)
            raise
        finally:
            # Record duration
            duration = time.perf_counter() - start_time
            self.record_duration(duration, attributes=attrs)


# Global instance for convenience
_metrics_api = MetricsAPI()


def get_meter() -> Meter:
    """Get the global OpenTelemetry meter instance.
    
    Returns:
        The OpenTelemetry Meter instance
    """
    return _metrics_api.meter


def create_counter(name: str, unit: str = "", description: str = "") -> Counter:
    """Create a counter metric using the global metrics API.
    
    Args:
        name: The name of the metric
        unit: The unit of measurement
        description: A description of what this metric measures
        
    Returns:
        A Counter instance
    """
    return _metrics_api.create_counter(name, unit, description)


def create_histogram(name: str, unit: str = "", description: str = "") -> Histogram:
    """Create a histogram metric using the global metrics API.
    
    Args:
        name: The name of the metric
        unit: The unit of measurement
        description: A description of what this metric measures
        
    Returns:
        A Histogram instance
    """
    return _metrics_api.create_histogram(name, unit, description)


def create_up_down_counter(name: str, unit: str = "", description: str = "") -> UpDownCounter:
    """Create an up-down counter metric using the global metrics API.
    
    Args:
        name: The name of the metric
        unit: The unit of measurement
        description: A description of what this metric measures
        
    Returns:
        An UpDownCounter instance
    """
    return _metrics_api.create_up_down_counter(name, unit, description)


def create_red_metrics(service_name: str) -> REDMetrics:
    """Create a REDMetrics helper for a service.
    
    Args:
        service_name: The name of the service
        
    Returns:
        A REDMetrics instance
    """
    return REDMetrics(service_name)