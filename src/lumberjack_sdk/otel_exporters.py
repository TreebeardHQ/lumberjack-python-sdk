"""
OpenTelemetry exporters that translate OTEL data to Lumberjack format.
"""
import json
import threading
import time
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Sequence

import requests
from opentelemetry.sdk._logs.export import LogExporter
from opentelemetry.sdk._logs import LogRecord
from opentelemetry.sdk.trace.export import SpanExporter, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

from .internal_utils.fallback_logger import sdk_logger


class LogSenderWorker(threading.Thread):
    """Worker thread to process sending requests asynchronously."""

    def __init__(self, send_queue: Queue):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._send_queue = send_queue

    def run(self) -> None:
        while True:
            send_fn = self._send_queue.get()
            if send_fn is None:  # shutdown signal
                break
            try:
                send_fn()
            except Exception as e:
                sdk_logger.error(f"Unexpected error in log sender: {str(e)}")
            finally:
                self._send_queue.task_done()

    def stop(self) -> None:
        self._stop_event.set()


class LumberjackSpanExporter(SpanExporter):
    """Custom OTEL span exporter that sends spans to Lumberjack in the expected format."""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        project_name: Optional[str] = None,
        registry: Optional[Any] = None,
        config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self._api_key = api_key
        self._endpoint = endpoint
        self._project_name = project_name
        self._registry = registry
        self._config_version = config_version
        self._update_callback = update_callback
        self._send_queue: Queue = Queue()
        self._worker: Optional[LogSenderWorker] = None
        self._worker_started = False

    def start_worker(self) -> None:
        """Start the background worker thread if not already started."""
        if not self._worker_started:
            if not self._worker or not self._worker.is_alive():
                self._worker = LogSenderWorker(self._send_queue)
                self._worker.start()
                sdk_logger.info("Lumberjack span worker started.")
            self._worker_started = True

    def stop_worker(self) -> None:
        """Stop the background worker thread."""
        if self._worker and self._worker.is_alive():
            self._worker.stop()
            self._worker.join(timeout=10)
            self._worker_started = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to Lumberjack."""
        if not spans:
            return SpanExportResult.SUCCESS

        try:
            # Convert OTEL spans to Lumberjack format
            lumberjack_spans = self._convert_spans(spans)
            
            # Send spans asynchronously
            def send_request():
                self._send_spans(lumberjack_spans)

            self._send_queue.put(send_request)
            return SpanExportResult.SUCCESS

        except Exception as e:
            sdk_logger.error(f"Error exporting spans: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self.stop_worker()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending spans."""
        # Wait for queue to be processed
        if self._worker and self._worker.is_alive():
            self._send_queue.join()
        return True

    def _convert_spans(self, otel_spans: Sequence[ReadableSpan]) -> List[Dict[str, Any]]:
        """Convert OTEL spans to Lumberjack span format."""
        lumberjack_spans = []
        
        for otel_span in otel_spans:
            # Convert to Lumberjack span format
            span_dict = {
                "traceId": format(otel_span.context.trace_id, '032x'),
                "spanId": format(otel_span.context.span_id, '016x'),
                "name": otel_span.name,
                "kind": otel_span.kind.value,
                "startTimeUnixNano": otel_span.start_time
            }

            # Add parent span ID if present
            if otel_span.parent and otel_span.parent.span_id:
                span_dict["parentSpanId"] = format(otel_span.parent.span_id, '016x')

            # Add end time if span is ended
            if otel_span.end_time:
                span_dict["endTimeUnixNano"] = otel_span.end_time

            # Convert attributes
            if otel_span.attributes:
                span_dict["attributes"] = [
                    {"key": k, "value": self._format_attribute_value(v)}
                    for k, v in otel_span.attributes.items()
                ]

            # Convert events
            if otel_span.events:
                span_dict["events"] = []
                for event in otel_span.events:
                    event_dict = {
                        "name": event.name,
                        "timeUnixNano": event.timestamp
                    }
                    if event.attributes:
                        event_dict["attributes"] = [
                            {"key": k, "value": self._format_attribute_value(v)}
                            for k, v in event.attributes.items()
                        ]
                    span_dict["events"].append(event_dict)

            # Convert links
            if otel_span.links:
                span_dict["links"] = []
                for link in otel_span.links:
                    link_dict = {
                        "traceId": format(link.context.trace_id, '032x'),
                        "spanId": format(link.context.span_id, '016x')
                    }
                    if link.attributes:
                        link_dict["attributes"] = [
                            {"key": k, "value": self._format_attribute_value(v)}
                            for k, v in link.attributes.items()
                        ]
                    span_dict["links"].append(link_dict)

            # Convert status
            if otel_span.status.status_code.value != 0:  # UNSET = 0
                span_dict["status"] = {
                    "code": otel_span.status.status_code.value
                }
                if otel_span.status.description:
                    span_dict["status"]["message"] = otel_span.status.description

            # Attach registered objects from registry if available
            if self._registry:
                try:
                    # Get objects relevant to this span's trace
                    trace_id = format(otel_span.context.trace_id, '032x')
                    objects = self._registry.get_objects_for_context(trace_id)
                    if objects:
                        span_dict["_lumberjack_objects"] = objects
                except Exception as e:
                    sdk_logger.debug(f"Could not attach registry objects: {e}")

            lumberjack_spans.append(span_dict)

        return lumberjack_spans

    def _format_attribute_value(self, value: Any) -> Dict[str, Any]:
        """Format attribute value according to OpenTelemetry spec."""
        if isinstance(value, str):
            return {"stringValue": value}
        elif isinstance(value, bool):
            return {"boolValue": value}
        elif isinstance(value, int):
            return {"intValue": value}
        elif isinstance(value, float):
            return {"doubleValue": value}
        else:
            return {"stringValue": str(value)}

    def _send_spans(self, spans: List[Dict[str, Any]]) -> None:
        """Send spans to the Lumberjack API in OpenTelemetry format."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }

        # Format spans as resource spans (compatible with existing format)
        resource_spans = self._format_spans_for_otel(spans)

        data = json.dumps({
            'resourceSpans': resource_spans,
            'project_name': self._project_name,
            "v": self._config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                sdk_logger.debug(f"Sending spans to {self._endpoint}")
                response = requests.post(self._endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(f"Spans sent successfully. spans sent: {len(spans)}")

                    result = response.json()

                    # Handle updated config
                    if (
                        isinstance(result, dict) and result.get('updated_config')
                        and self._update_callback
                    ):
                        self._update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("error while sending spans", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send spans failed.")

    def _format_spans_for_otel(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format spans into OpenTelemetry ResourceSpans structure."""
        if not spans:
            return []

        # Group spans by service (project) name
        scope_spans = [{
            "scope": {
                "name": "lumberjack-python-sdk",
                "version": "2.0"
            },
            "spans": spans
        }]

        # Create resource with service name
        resource_attributes = []
        if self._project_name:
            resource_attributes.append({
                "key": "service.name",
                "value": {"stringValue": self._project_name}
            })

        return [{
            "resource": {
                "attributes": resource_attributes
            },
            "scopeSpans": scope_spans
        }]


class LumberjackLogExporter(LogExporter):
    """Custom OTEL log exporter that sends logs to Lumberjack in the expected format."""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        project_name: Optional[str] = None,
        config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self._api_key = api_key
        self._endpoint = endpoint
        self._project_name = project_name
        self._config_version = config_version
        self._update_callback = update_callback
        self._send_queue: Queue = Queue()
        self._worker: Optional[LogSenderWorker] = None
        self._worker_started = False

    def start_worker(self) -> None:
        """Start the background worker thread if not already started."""
        if not self._worker_started:
            if not self._worker or not self._worker.is_alive():
                self._worker = LogSenderWorker(self._send_queue)
                self._worker.start()
                sdk_logger.info("Lumberjack log worker started.")
            self._worker_started = True

    def stop_worker(self) -> None:
        """Stop the background worker thread."""
        if self._worker and self._worker.is_alive():
            self._worker.stop()
            self._worker.join(timeout=10)
            self._worker_started = False

    def export(self, log_records: Sequence[Any]) -> bool:
        """Export log records to Lumberjack."""
        if not log_records:
            return True

        try:
            # Convert OTEL log records to Lumberjack format
            lumberjack_logs = self._convert_log_records(log_records)
            
            # Send logs asynchronously
            def send_request():
                self._send_logs(lumberjack_logs)

            self._send_queue.put(send_request)
            return True

        except Exception as e:
            sdk_logger.error(f"Error exporting logs: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self.stop_worker()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending logs."""
        # Wait for queue to be processed
        if self._worker and self._worker.is_alive():
            self._send_queue.join()
        return True

    def _convert_log_records(self, otel_logs: Sequence[Any]) -> List[Dict[str, Any]]:
        """Convert OTEL log records to Lumberjack log format."""
        lumberjack_logs = []
        
        for log_data in otel_logs:
            # Convert to Lumberjack log format
            # log_data is a LogData object from the batch processor
            log_record = log_data.log_record
            
            log_dict = {
                "timestamp": getattr(log_record, 'timestamp', None) or getattr(log_record, 'observed_timestamp', None),
                "message": str(log_record.body) if log_record.body else "",
                "level": self._map_severity_to_level(log_record.severity_number),
            }

            # Add trace context if available
            if hasattr(log_record, 'trace_id') and log_record.trace_id:
                log_dict["trace_id"] = format(log_record.trace_id, '032x')
            if hasattr(log_record, 'span_id') and log_record.span_id:
                log_dict["span_id"] = format(log_record.span_id, '016x')

            # Add attributes
            if hasattr(log_record, 'attributes') and log_record.attributes:
                for key, value in log_record.attributes.items():
                    log_dict[key] = value

            # Add resource attributes
            if hasattr(log_data, 'resource') and log_data.resource and log_data.resource.attributes:
                for key, value in log_data.resource.attributes.items():
                    if key.startswith("service."):
                        log_dict[key] = value

            lumberjack_logs.append(log_dict)

        return lumberjack_logs

    def _map_severity_to_level(self, severity_number: Optional[int]) -> str:
        """Map OTEL severity number to Lumberjack level string."""
        if severity_number is None:
            return "info"
        
        # Map based on OTEL severity number ranges
        if severity_number >= 17:  # ERROR
            return "error"
        elif severity_number >= 13:  # WARN
            return "warning"
        elif severity_number >= 9:  # INFO
            return "info"
        elif severity_number >= 5:  # DEBUG
            return "debug"
        else:  # TRACE
            return "trace"

    def _send_logs(self, logs: List[Dict[str, Any]]) -> None:
        """Send logs to the Lumberjack API."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }
        data = json.dumps({
            'logs': logs,
            'project_name': self._project_name,
            "v": self._config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                response = requests.post(self._endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(f"Logs sent successfully. logs sent: {len(logs)}")

                    result = response.json()

                    # Handle updated config
                    if (
                        isinstance(result, dict) and result.get('updated_config')
                        and self._update_callback
                    ):
                        self._update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("error while sending logs", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send logs failed.")