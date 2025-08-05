"""
Export functionality for sending logs, objects, and spans to the Lumberjack API.
"""
import json
import threading
import time
from queue import Queue
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence

import requests
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk._logs.export import LogExporter, LogExportResult
from opentelemetry.sdk._logs import LogRecord
from opentelemetry.trace import Span as OtelSpan

from .internal_utils.fallback_logger import sdk_logger

if TYPE_CHECKING:
    from .spans import Span


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
                sdk_logger.error(
                    f"Unexpected error in log sender: {str(e)}")
            finally:
                self._send_queue.task_done()

    def stop(self) -> None:
        self._stop_event.set()


class LumberjackExporter:
    """Handles exporting logs, objects, and spans to the Lumberjack API."""

    def __init__(
        self, api_key: str, endpoint: str, objects_endpoint: str,
        spans_endpoint: Optional[str] = None, project_name: Optional[str] = None
    ):
        self._api_key = api_key
        self._endpoint = endpoint
        self._objects_endpoint = objects_endpoint
        self._spans_endpoint = spans_endpoint or endpoint.replace(
            '/logs/batch', '/spans/batch')
        self._project_name = project_name
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

    def send_logs_async(
        self, logs: List[Any], config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Queue logs to be sent asynchronously."""
        def send_request():
            self._send_logs(logs, config_version, update_callback)

        self._send_queue.put(send_request)

    def send_objects_async(
        self, objects: List[Dict[str, Any]], config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Queue objects to be sent asynchronously."""
        def send_request():
            self._send_objects(objects, config_version, update_callback)

        self._send_queue.put(send_request)

    def send_spans_async(
        self, spans: List["Span"], config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Queue spans to be sent asynchronously."""
        def send_request():
            self._send_spans(spans, config_version, update_callback)

        self._send_queue.put(send_request)

    def _send_logs(self, logs: List[Any], config_version: Optional[int] = None,
                   update_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Send logs to the Lumberjack API."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }
        data = json.dumps({
            'logs': logs,
            'project_name': self._project_name,
            "v": config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self._endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(
                        f"Logs sent successfully. logs sent: {len(logs)}")

                    result = response.json()

                    # we get an updated config if the server has a later config version than we
                    # sent it
                    if (
                        isinstance(result, dict) and result.get(
                            'updated_config')
                        and update_callback
                    ):
                        update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("error while sending logs", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send logs failed.")

    def _send_objects(self, objects: List[Dict[str, Any]], config_version: Optional[int] = None,
                      update_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Send object registrations to the API."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }
        data = json.dumps({
            'objects': objects,
            'project_name': self._project_name,
            "v": config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                sdk_logger.warning(
                    f"Sending objects to {self._objects_endpoint}")
                response = requests.post(
                    self._objects_endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(
                        f"Objects sent successfully. objects sent: {len(objects)}")

                    result = response.json()

                    # we get an updated config if the server has a later config version than we
                    # sent it
                    if (
                        isinstance(result, dict) and result.get(
                            'updated_config')
                        and update_callback
                    ):
                        update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("error while sending objects", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send objects failed.")

    def _send_spans(
        self, spans: List["Span"], config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Send spans to the Lumberjack API in OpenTelemetry format."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }

        # Convert spans to OpenTelemetry format
        resource_spans = self._format_spans_for_otel(spans)

        data = json.dumps({
            'resourceSpans': resource_spans,
            'project_name': self._project_name,
            "v": config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                sdk_logger.debug(f"Sending spans to {self._spans_endpoint}")
                response = requests.post(
                    self._spans_endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(
                        f"Spans sent successfully. spans sent: {len(spans)}")

                    result = response.json()

                    # we get an updated config if the server has a later config version than we
                    # sent it
                    if (
                        isinstance(result, dict) and result.get(
                            'updated_config')
                        and update_callback
                    ):
                        update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text} {self._spans_endpoint}")
            except Exception as e:
                sdk_logger.error("error while sending spans", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send spans failed.")

    def _format_spans_for_otel(self, spans: List["Span"]) -> List[Dict[str, Any]]:
        """Format spans into OpenTelemetry ResourceSpans structure."""
        if not spans:
            return []

        # Group spans by service (project) name
        scope_spans = []
        otel_spans = []

        for span in spans:
            otel_spans.append(span.to_otel_dict())

        scope_spans.append({
            "scope": {
                "name": "lumberjack-python-sdk",
                "version": "2.0"
            },
            "spans": otel_spans
        })

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


class LumberjackSpanExporter(SpanExporter):
    """OpenTelemetry SpanExporter that sends spans to Lumberjack backend."""

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
        self._shutdown = False

    def export(self, spans: Sequence[OtelSpan]) -> SpanExportResult:
        """Export spans to Lumberjack backend."""
        if self._shutdown:
            return SpanExportResult.FAILURE

        try:
            # Convert OTel spans to Lumberjack format
            formatted_spans = self._format_spans(spans)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._api_key}'
            }
            
            # Create OpenTelemetry-compliant resource spans structure
            resource_spans = self._create_resource_spans(formatted_spans)
            
            data = json.dumps({
                'resourceSpans': resource_spans,
                'project_name': self._project_name,
                "v": self._config_version,
                "sdk_version": 2
            })

            response = requests.post(
                self._endpoint, headers=headers, data=data, timeout=30
            )
            
            if response.ok:
                sdk_logger.debug(
                    f"Spans exported successfully. Count: {len(spans)}"
                )
                
                result = response.json()
                if (
                    isinstance(result, dict) and 
                    result.get('updated_config') and 
                    self._update_callback
                ):
                    self._update_callback(result.get('updated_config'))
                
                return SpanExportResult.SUCCESS
            else:
                sdk_logger.warning(
                    f"Failed to export spans: {response.status_code} - {response.text}"
                )
                return SpanExportResult.FAILURE
                
        except Exception as e:
            sdk_logger.error(f"Error exporting spans: {str(e)}", exc_info=True)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self._shutdown = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending spans."""
        # No buffering in this implementation
        return True

    def _format_spans(self, spans: Sequence[OtelSpan]) -> List[Dict[str, Any]]:
        """Convert OpenTelemetry spans to dictionaries."""
        formatted_spans = []
        
        for span in spans:
            span_context = span.get_span_context()
            
            formatted_span = {
                "traceId": format(span_context.trace_id, "032x"),
                "spanId": format(span_context.span_id, "016x"),
                "name": span.name,
                "kind": span.kind.value,
                "startTimeUnixNano": span.start_time,
                "endTimeUnixNano": span.end_time,
                "status": {
                    "code": span.status.status_code.value
                }
            }
            
            if span.parent and span.parent.span_id:
                formatted_span["parentSpanId"] = format(span.parent.span_id, "016x")
            
            if span.status.description:
                formatted_span["status"]["message"] = span.status.description
            
            # Format attributes
            if span.attributes:
                formatted_span["attributes"] = [
                    {"key": k, "value": self._format_attribute_value(v)}
                    for k, v in span.attributes.items()
                ]
            
            # Format events
            if span.events:
                formatted_span["events"] = [
                    {
                        "name": event.name,
                        "timeUnixNano": event.timestamp,
                        "attributes": [
                            {"key": k, "value": self._format_attribute_value(v)}
                            for k, v in (event.attributes or {}).items()
                        ]
                    }
                    for event in span.events
                ]
            
            # Format links
            if span.links:
                formatted_span["links"] = [
                    {
                        "traceId": format(link.context.trace_id, "032x"),
                        "spanId": format(link.context.span_id, "016x"),
                        "attributes": [
                            {"key": k, "value": self._format_attribute_value(v)}
                            for k, v in (link.attributes or {}).items()
                        ]
                    }
                    for link in span.links
                ]
            
            formatted_spans.append(formatted_span)
        
        return formatted_spans

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
        elif isinstance(value, (list, tuple)):
            return {"arrayValue": {"values": [self._format_attribute_value(v) for v in value]}}
        else:
            return {"stringValue": str(value)}

    def _create_resource_spans(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create OpenTelemetry ResourceSpans structure."""
        scope_spans = [{
            "scope": {
                "name": "lumberjack-python-sdk",
                "version": "2.0"
            },
            "spans": spans
        }]
        
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
    """OpenTelemetry LogExporter that sends logs to Lumberjack backend."""

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
        self._shutdown = False

    def export(self, batch: Sequence[LogRecord]) -> LogExportResult:
        """Export logs to Lumberjack backend."""
        if self._shutdown:
            return LogExportResult.FAILURE

        try:
            # Convert OTel LogRecords to Lumberjack format
            formatted_logs = self._format_logs(batch)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._api_key}'
            }
            
            data = json.dumps({
                'logs': formatted_logs,
                'project_name': self._project_name,
                "v": self._config_version,
                "sdk_version": 2
            })

            response = requests.post(
                self._endpoint, headers=headers, data=data, timeout=30
            )
            
            if response.ok:
                sdk_logger.debug(
                    f"Logs exported successfully. Count: {len(batch)}"
                )
                
                result = response.json()
                if (
                    isinstance(result, dict) and 
                    result.get('updated_config') and 
                    self._update_callback
                ):
                    self._update_callback(result.get('updated_config'))
                
                return LogExportResult.SUCCESS
            else:
                sdk_logger.warning(
                    f"Failed to export logs: {response.status_code} - {response.text}"
                )
                return LogExportResult.FAILURE
                
        except Exception as e:
            sdk_logger.error(f"Error exporting logs: {str(e)}", exc_info=True)
            return LogExportResult.FAILURE

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self._shutdown = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending logs."""
        # No buffering in this implementation
        return True

    def _format_logs(self, logs: Sequence[LogRecord]) -> List[Dict[str, Any]]:
        """Convert OpenTelemetry LogRecords to Lumberjack format."""
        from .constants import (
            COMPACT_TS_KEY, COMPACT_TRACE_ID_KEY, COMPACT_SPAN_ID_KEY,
            COMPACT_MESSAGE_KEY, COMPACT_LEVEL_KEY, COMPACT_FILE_KEY,
            COMPACT_LINE_KEY, COMPACT_TRACEBACK_KEY, COMPACT_SOURCE_KEY,
            COMPACT_FUNCTION_KEY, COMPACT_EXEC_TYPE_KEY, COMPACT_EXEC_VALUE_KEY
        )
        
        formatted_logs = []
        
        for log_record in logs:
            # Start with basic fields
            formatted_log = {
                COMPACT_TS_KEY: log_record.timestamp // 1_000_000,  # Convert nanoseconds to milliseconds
                COMPACT_MESSAGE_KEY: log_record.body or "",
                COMPACT_LEVEL_KEY: self._severity_to_level(log_record.severity_number),
                COMPACT_SOURCE_KEY: "lumberjack"
            }
            
            # Add trace context if available
            if log_record.trace_id and log_record.trace_id != 0:
                formatted_log[COMPACT_TRACE_ID_KEY] = format(log_record.trace_id, "032x")
            if log_record.span_id and log_record.span_id != 0:
                formatted_log[COMPACT_SPAN_ID_KEY] = format(log_record.span_id, "016x")
            
            # Extract attributes and map to Lumberjack format
            if log_record.attributes:
                # Look for standard fields
                formatted_log[COMPACT_FILE_KEY] = log_record.attributes.get("code.filepath", "")
                formatted_log[COMPACT_LINE_KEY] = log_record.attributes.get("code.lineno", "")
                formatted_log[COMPACT_FUNCTION_KEY] = log_record.attributes.get("code.function", "")
                
                # Exception info
                if "exception.type" in log_record.attributes:
                    formatted_log[COMPACT_EXEC_TYPE_KEY] = log_record.attributes.get("exception.type", "")
                    formatted_log[COMPACT_EXEC_VALUE_KEY] = log_record.attributes.get("exception.message", "")
                    formatted_log[COMPACT_TRACEBACK_KEY] = log_record.attributes.get("exception.stacktrace", "")
                
                # Source override
                if "source" in log_record.attributes:
                    formatted_log[COMPACT_SOURCE_KEY] = log_record.attributes["source"]
                
                # Collect remaining attributes as props
                props = {}
                standard_keys = {
                    "code.filepath", "code.lineno", "code.function",
                    "exception.type", "exception.message", "exception.stacktrace",
                    "source"
                }
                
                for key, value in log_record.attributes.items():
                    if key not in standard_keys:
                        props[key] = value
                
                if props:
                    formatted_log["props"] = props
            
            formatted_logs.append(formatted_log)
        
        return formatted_logs

    def _severity_to_level(self, severity_number: Optional[int]) -> str:
        """Convert OpenTelemetry severity number to Lumberjack level."""
        if severity_number is None:
            return "info"
        
        # OpenTelemetry severity mapping
        if severity_number <= 4:  # TRACE
            return "trace"
        elif severity_number <= 8:  # DEBUG
            return "debug"
        elif severity_number <= 12:  # INFO
            return "info"
        elif severity_number <= 16:  # WARN
            return "warning"
        elif severity_number <= 20:  # ERROR
            return "error"
        else:  # FATAL
            return "critical"
