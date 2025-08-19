from .internal_utils.fallback_logger import sdk_logger as sdk_logger
from _typeshed import Incomplete
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricExporter as MetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource as Resource
from typing import Any

OTLP_AVAILABLE: bool

class LumberjackMetricsExporter:
    api_key: Incomplete
    endpoint: Incomplete
    project_name: Incomplete
    config_version: Incomplete
    update_callback: Incomplete
    exporter: Incomplete
    def __init__(self, api_key: str, endpoint: str, project_name: str | None = None, config_version: int | None = None, update_callback: Any | None = None) -> None: ...
    def get_exporter(self) -> MetricExporter: ...
    def shutdown(self) -> None: ...

def create_metrics_reader(exporter: MetricExporter, export_interval_millis: int = 60000, export_timeout_millis: int = 30000) -> PeriodicExportingMetricReader: ...
def create_console_metrics_reader(export_interval_millis: int = 60000, export_timeout_millis: int = 30000) -> PeriodicExportingMetricReader: ...
def create_meter_provider(resource: Resource, metric_readers: list | None = None) -> MeterProvider: ...
