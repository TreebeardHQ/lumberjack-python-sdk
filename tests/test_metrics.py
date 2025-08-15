"""
Unit tests for Lumberjack metrics functionality.
"""

import time
import unittest
from typing import List, Sequence
from unittest.mock import MagicMock, patch

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

from lumberjack_sdk import Lumberjack
from lumberjack_sdk.metrics import (
    MetricsAPI,
    REDMetrics,
    create_counter,
    create_histogram,
    create_red_metrics,
    create_up_down_counter,
    get_meter,
)


class MockMetricExporter(MetricExporter):
    """Mock metric exporter that captures metrics for testing."""
    
    def __init__(self):
        super().__init__()
        self.metrics: List[MetricsData] = []
        self.export_count = 0
        self.shutdown_called = False
        self.force_flush_called = False
    
    def export(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10_000,
        **kwargs,
    ) -> MetricExportResult:
        """Export metrics data."""
        self.metrics.append(metrics_data)
        self.export_count += 1
        return MetricExportResult.SUCCESS
    
    def shutdown(self, timeout_millis: float = 30_000, **kwargs):
        """Shutdown the exporter."""
        self.shutdown_called = True
    
    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        """Force flush any pending metrics."""
        self.force_flush_called = True
        return True
    
    def get_all_metrics(self):
        """Get all captured metrics as a flat list."""
        all_metrics = []
        for metrics_data in self.metrics:
            for resource_metric in metrics_data.resource_metrics:
                for scope_metric in resource_metric.scope_metrics:
                    for metric in scope_metric.metrics:
                        all_metrics.append({
                            'name': metric.name,
                            'description': metric.description,
                            'unit': metric.unit,
                            'data': metric.data,
                        })
        return all_metrics
    
    def get_metric_by_name(self, name: str):
        """Get a specific metric by name."""
        for metric in self.get_all_metrics():
            if metric['name'] == name:
                return metric
        return None
    
    def reset(self):
        """Reset the captured metrics."""
        self.metrics = []
        self.export_count = 0


class TestMetricsEndToEnd(unittest.TestCase):
    """Test metrics functionality end-to-end with mock exporter."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Reset Lumberjack
        Lumberjack.reset()
        
        # Reset MetricsAPI singleton
        MetricsAPI._instance = None
        MetricsAPI._meter = None
        
        # Create mock exporter
        self.mock_exporter = MockMetricExporter()
        
        # Initialize Lumberjack with mock exporter
        Lumberjack.init(
            project_name="test_metrics",
            custom_metrics_exporter=self.mock_exporter,
            debug_mode=True,
        )
        
        # Get the instance
        self.lumberjack = Lumberjack.get_instance()
    
    def tearDown(self):
        """Clean up after tests."""
        # Shutdown Lumberjack
        if self.lumberjack and self.lumberjack._initialized:
            self.lumberjack.shutdown()
        Lumberjack.reset()
        
        # Reset singleton
        MetricsAPI._instance = None
        MetricsAPI._meter = None
    
    def test_counter_metric(self):
        """Test counter metric functionality."""
        # Create a counter
        counter = create_counter(
            name="test_requests",
            unit="1",
            description="Test request counter"
        )
        
        # Add some values
        counter.add(1, attributes={"endpoint": "/api/v1"})
        counter.add(2, attributes={"endpoint": "/api/v1"})
        counter.add(3, attributes={"endpoint": "/api/v2"})
        
        # Force flush metrics
        self.lumberjack._meter_provider.force_flush()
        
        # Check that metrics were exported
        self.assertGreater(self.mock_exporter.export_count, 0)
        
        # Get the counter metric
        metric = self.mock_exporter.get_metric_by_name("test_requests")
        self.assertIsNotNone(metric)
        self.assertEqual(metric['unit'], "1")
        self.assertEqual(metric['description'], "Test request counter")
        
        # Check the data points
        total_value = 0
        for data_point in metric['data'].data_points:
            total_value += data_point.value
        
        self.assertEqual(total_value, 6)  # 1 + 2 + 3
    
    def test_histogram_metric(self):
        """Test histogram metric functionality."""
        # Create a histogram
        histogram = create_histogram(
            name="response_time",
            unit="ms",
            description="Response time histogram"
        )
        
        # Record some values
        histogram.record(100, attributes={"endpoint": "/api"})
        histogram.record(200, attributes={"endpoint": "/api"})
        histogram.record(150, attributes={"endpoint": "/api"})
        histogram.record(50, attributes={"endpoint": "/health"})
        
        # Force flush metrics
        self.lumberjack._meter_provider.force_flush()
        
        # Check that metrics were exported
        self.assertGreater(self.mock_exporter.export_count, 0)
        
        # Get the histogram metric
        metric = self.mock_exporter.get_metric_by_name("response_time")
        self.assertIsNotNone(metric)
        self.assertEqual(metric['unit'], "ms")
        
        # Check the data points
        total_sum = 0
        total_count = 0
        for data_point in metric['data'].data_points:
            total_sum += data_point.sum
            total_count += data_point.count
        
        self.assertEqual(total_count, 4)
        self.assertEqual(total_sum, 500)  # 100 + 200 + 150 + 50
    
    def test_up_down_counter_metric(self):
        """Test up-down counter metric functionality."""
        # Create an up-down counter
        counter = create_up_down_counter(
            name="active_connections",
            unit="1",
            description="Active connections"
        )
        
        # Add and subtract values
        counter.add(5, attributes={"server": "web1"})
        counter.add(3, attributes={"server": "web1"})
        counter.add(-2, attributes={"server": "web1"})
        counter.add(4, attributes={"server": "web2"})
        
        # Force flush metrics
        self.lumberjack._meter_provider.force_flush()
        
        # Check that metrics were exported
        self.assertGreater(self.mock_exporter.export_count, 0)
        
        # Get the metric
        metric = self.mock_exporter.get_metric_by_name("active_connections")
        self.assertIsNotNone(metric)
        
        # Check the data points
        total_value = 0
        for data_point in metric['data'].data_points:
            total_value += data_point.value
        
        self.assertEqual(total_value, 10)  # 5 + 3 - 2 + 4
    
    def test_red_metrics(self):
        """Test RED metrics helper."""
        # Create RED metrics
        red = create_red_metrics("api_service")
        
        # Record some requests with context manager
        with red.measure(operation="get_user", attributes={"user_id": "123"}):
            time.sleep(0.01)
        
        with red.measure(operation="get_user", attributes={"user_id": "456"}):
            time.sleep(0.02)
        
        # Record an error
        try:
            with red.measure(operation="get_user", attributes={"user_id": "invalid"}):
                raise ValueError("User not found")
        except ValueError:
            pass
        
        # Manual recording
        red.record_request(attributes={"operation": "list_users"})
        red.record_duration(0.05, attributes={"operation": "list_users"})
        red.record_error(attributes={"operation": "delete_user", "error": "forbidden"})
        
        # Force flush metrics
        self.lumberjack._meter_provider.force_flush()
        
        # Check that metrics were exported
        self.assertGreater(self.mock_exporter.export_count, 0)
        
        # Check requests counter
        requests_metric = self.mock_exporter.get_metric_by_name("api_service_requests_total")
        self.assertIsNotNone(requests_metric)
        total_requests = sum(dp.value for dp in requests_metric['data'].data_points)
        self.assertEqual(total_requests, 4)  # 3 context managers + 1 manual
        
        # Check errors counter
        errors_metric = self.mock_exporter.get_metric_by_name("api_service_errors_total")
        self.assertIsNotNone(errors_metric)
        total_errors = sum(dp.value for dp in errors_metric['data'].data_points)
        self.assertEqual(total_errors, 2)  # 1 from context manager + 1 manual
        
        # Check duration histogram
        duration_metric = self.mock_exporter.get_metric_by_name("api_service_request_duration_seconds")
        self.assertIsNotNone(duration_metric)
        total_count = sum(dp.count for dp in duration_metric['data'].data_points)
        self.assertEqual(total_count, 4)  # 3 context managers + 1 manual
    
    def test_observable_metrics(self):
        """Test observable metrics (async metrics)."""
        from opentelemetry.metrics import CallbackOptions, Observation
        
        # Create a counter for testing
        call_count = {'cpu': 0, 'memory': 0}
        
        def get_cpu_usage(options: CallbackOptions):
            call_count['cpu'] += 1
            return [Observation(value=50.5, attributes={"host": "test-host"})]
        
        def get_memory_usage(options: CallbackOptions):
            call_count['memory'] += 1
            return [Observation(value=1024, attributes={"host": "test-host"})]
        
        # Get meter and create observable gauges
        meter = get_meter()
        cpu_gauge = meter.create_observable_gauge(
            name="cpu_usage",
            callbacks=[get_cpu_usage],
            unit="%",
            description="CPU usage percentage"
        )
        
        memory_gauge = meter.create_observable_gauge(
            name="memory_usage",
            callbacks=[get_memory_usage],
            unit="MB",
            description="Memory usage in MB"
        )
        
        # Force collection multiple times
        for _ in range(3):
            self.lumberjack._meter_provider.force_flush()
            time.sleep(0.01)
        
        # Check that callbacks were invoked
        self.assertGreater(call_count['cpu'], 0)
        self.assertGreater(call_count['memory'], 0)
        
        # Check that metrics were exported
        self.assertGreater(self.mock_exporter.export_count, 0)
        
        # Check the metrics
        cpu_metric = self.mock_exporter.get_metric_by_name("cpu_usage")
        self.assertIsNotNone(cpu_metric)
        self.assertEqual(cpu_metric['unit'], "%")
        
        memory_metric = self.mock_exporter.get_metric_by_name("memory_usage")
        self.assertIsNotNone(memory_metric)
        self.assertEqual(memory_metric['unit'], "MB")
    
    def test_metrics_with_attributes(self):
        """Test that metrics properly handle attributes."""
        counter = create_counter("test_counter")
        
        # Add values with different attributes
        counter.add(1, attributes={"env": "prod", "region": "us-east"})
        counter.add(2, attributes={"env": "prod", "region": "us-west"})
        counter.add(3, attributes={"env": "dev", "region": "us-east"})
        
        # Force flush
        self.lumberjack._meter_provider.force_flush()
        
        # Get the metric
        metric = self.mock_exporter.get_metric_by_name("test_counter")
        self.assertIsNotNone(metric)
        
        # Check that we have multiple data points with different attributes
        data_points = list(metric['data'].data_points)
        self.assertGreater(len(data_points), 0)
        
        # Check that attributes are preserved
        attributes_seen = set()
        for dp in data_points:
            if hasattr(dp, 'attributes') and dp.attributes:
                attr_tuple = tuple(sorted(dp.attributes.items()))
                attributes_seen.add(attr_tuple)
        
        # We should see different attribute combinations
        self.assertGreater(len(attributes_seen), 0)


class TestMetricsIntegration(unittest.TestCase):
    """Test metrics integration with Lumberjack core."""
    
    def setUp(self):
        """Set up test fixtures."""
        Lumberjack.reset()
        MetricsAPI._instance = None
        MetricsAPI._meter = None
    
    def tearDown(self):
        """Clean up after tests."""
        instance = Lumberjack.get_instance()
        if instance and instance._initialized:
            instance.shutdown()
        Lumberjack.reset()
        MetricsAPI._instance = None
        MetricsAPI._meter = None
    
    def test_metrics_provider_initialization(self):
        """Test that metrics provider is initialized with Lumberjack."""
        Lumberjack.init(
            project_name="test_metrics",
            debug_mode=True
        )
        
        instance = Lumberjack.get_instance()
        self.assertIsNotNone(instance._meter_provider)
        self.assertIsNotNone(instance.meter)
    
    def test_metrics_with_custom_exporter(self):
        """Test using a custom metrics exporter."""
        mock_exporter = MockMetricExporter()
        
        Lumberjack.init(
            project_name="test_custom",
            custom_metrics_exporter=mock_exporter,
            debug_mode=True
        )
        
        instance = Lumberjack.get_instance()
        self.assertIsNotNone(instance._meter_provider)
        self.assertEqual(instance._metrics_exporter, mock_exporter)
        
        # Create and use a metric
        counter = create_counter("test_metric")
        counter.add(1)
        
        # Force flush
        instance._meter_provider.force_flush()
        
        # Check that the mock exporter received metrics
        self.assertGreater(mock_exporter.export_count, 0)
    
    def test_metrics_without_endpoint(self):
        """Test that metrics work even without a metrics_endpoint configured."""
        Lumberjack.init(
            project_name="test_no_endpoint",
            debug_mode=True
            # Note: no metrics_endpoint provided
        )
        
        instance = Lumberjack.get_instance()
        self.assertIsNotNone(instance._meter_provider)
        
        # Should still be able to create metrics (they just won't be exported)
        counter = create_counter("test_metric")
        counter.add(1)
        
        # This should not raise an error
        instance._meter_provider.force_flush()
    
    def test_metrics_singleton_pattern(self):
        """Test that MetricsAPI maintains singleton pattern."""
        Lumberjack.init(project_name="test", debug_mode=True)
        
        api1 = MetricsAPI()
        api2 = MetricsAPI()
        
        self.assertIs(api1, api2)
        self.assertIs(api1.meter, api2.meter)


if __name__ == "__main__":
    unittest.main()