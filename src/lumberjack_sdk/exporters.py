"""
Export functionality for sending logs, objects, and spans to the Lumberjack API.
"""
import json
from typing import  Any, Callable, Dict, List, Optional, Sequence, cast

import requests
from opentelemetry.sdk._logs import LogRecord, LogData  # type: ignore[attr-defined]
from opentelemetry._logs import SeverityNumber  # type: ignore[attr-defined]
from opentelemetry.sdk._logs.export import LogExporter, LogExportResult  # type: ignore[attr-defined]
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace import ReadableSpan

from .internal_utils.fallback_logger import sdk_logger



class LumberjackSpanExporter(SpanExporter):
    """OpenTelemetry SpanExporter that sends spans to Lumberjack backend."""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        project_name: Optional[str] = None,
        config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        self._api_key: str = api_key
        self._endpoint: str = endpoint
        self._project_name: Optional[str] = project_name
        self._config_version: Optional[int] = config_version
        self._update_callback: Optional[Callable[[Dict[str, Any]], None]] = update_callback
        self._shutdown: bool = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to Lumberjack backend."""
        if self._shutdown:
            return SpanExportResult.FAILURE

        try:
            # Convert OTel spans to Lumberjack format
            formatted_spans = self._format_spans(spans)
            
            headers: Dict[str, str] = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._api_key}'
            }
            
            # Create OpenTelemetry-compliant resource spans structure
            resource_spans: List[Dict[str, Any]] = self._create_resource_spans(formatted_spans)
            
            data: str = json.dumps({
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
                
                result: Dict[str, Any] = response.json()
                if self._update_callback:
                    updated_config = result.get('updated_config')
                    if updated_config and isinstance(updated_config, dict):
                        self._update_callback(cast(Dict[str, Any], updated_config))
                
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

    def _format_spans(self, spans: Sequence[ReadableSpan]) -> List[Dict[str, Any]]:
        """Convert OpenTelemetry spans to dictionaries."""
        formatted_spans: List[Dict[str, Any]] = []
        
        for span in spans:
            span_context = span.get_span_context()
            if not span_context:
                continue
                
            formatted_span: Dict[str, Any] = {
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
            
            if span.parent and hasattr(span.parent, 'span_id') and span.parent.span_id:
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
            return {"arrayValue": {"values": [self._format_attribute_value(v) for v in cast(Sequence[Any], value)]}}
        else:
            return {"stringValue": str(value)}

    def _create_resource_spans(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create OpenTelemetry ResourceSpans structure."""
        scope_spans: List[Dict[str, Any]] = [{
            "scope": {
                "name": "lumberjack-python-sdk",
                "version": "2.0"
            },
            "spans": spans
        }]
        
        resource_attributes: List[Dict[str, Any]] = []
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
    ) -> None:
        self._api_key: str = api_key
        self._endpoint: str = endpoint
        self._project_name: Optional[str] = project_name
        self._config_version: Optional[int] = config_version
        self._update_callback: Optional[Callable[[Dict[str, Any]], None]] = update_callback
        self._shutdown: bool = False

    def export(self, batch: Sequence[LogData]) -> LogExportResult:  # type: ignore[override]
        """Export logs to Lumberjack backend."""
        if self._shutdown:
            return LogExportResult.FAILURE

        try:
            # Extract LogRecords from LogData and convert to Lumberjack format
            log_records = [log_data.log_record for log_data in batch]
            formatted_logs: List[Dict[str, Any]] = self._format_logs(log_records)
            
            headers: Dict[str, str] = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._api_key}'
            }
            
            data: str = json.dumps({
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
                
                result: Dict[str, Any] = response.json()
                if self._update_callback:
                    updated_config = result.get('updated_config')
                    if updated_config and isinstance(updated_config, dict):
                        self._update_callback(cast(Dict[str, Any], updated_config))
                
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
            COMPACT_EXEC_TYPE_KEY,
            COMPACT_EXEC_VALUE_KEY,
            COMPACT_FILE_KEY,
            COMPACT_FUNCTION_KEY,
            COMPACT_LEVEL_KEY,
            COMPACT_LINE_KEY,
            COMPACT_MESSAGE_KEY,
            COMPACT_SOURCE_KEY,
            COMPACT_SPAN_ID_KEY,
            COMPACT_TRACE_ID_KEY,
            COMPACT_TRACEBACK_KEY,
            COMPACT_TS_KEY,
        )
        
        formatted_logs: List[Dict[str, Any]] = []
        
        for log_record in logs:
            # log_record is already a LogRecord, no need to extract
            
            # Start with basic fields
            formatted_log: Dict[str, Any] = {
                # Convert nanoseconds to milliseconds
                COMPACT_TS_KEY: (log_record.timestamp or 0) // 1_000_000,
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
                    formatted_log[COMPACT_EXEC_TYPE_KEY] = log_record.attributes.get(
                        "exception.type", ""
                    )
                    formatted_log[COMPACT_EXEC_VALUE_KEY] = log_record.attributes.get(
                        "exception.message", ""
                    )
                    formatted_log[COMPACT_TRACEBACK_KEY] = log_record.attributes.get(
                        "exception.stacktrace", ""
                    )
                
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

    def _severity_to_level(self, severity_number: Optional[SeverityNumber]) -> str:
        """Convert OpenTelemetry severity number to Lumberjack level."""
        if severity_number is None:
            return "info"
        
        # Convert SeverityNumber to its numeric value
        severity_value = severity_number.value
        
        # OpenTelemetry severity mapping
        if severity_value <= 4:  # TRACE
            return "trace"
        elif severity_value <= 8:  # DEBUG
            return "debug"
        elif severity_value <= 12:  # INFO
            return "info"
        elif severity_value <= 16:  # WARN
            return "warning"
        elif severity_value <= 20:  # ERROR
            return "error"
        else:  # FATAL
            return "critical"
