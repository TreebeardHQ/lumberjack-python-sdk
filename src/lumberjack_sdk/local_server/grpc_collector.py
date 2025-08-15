"""
GRPC collector for OpenTelemetry logs.

Receives OTLP log data via GRPC and stores it in the local database.
"""
import asyncio
import time
from concurrent import futures
from typing import List, Optional, Any, Dict

import grpc
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2_grpc, logs_service_pb2
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.logs.v1 import logs_pb2
from opentelemetry.proto.resource.v1 import resource_pb2

from .database import LogEntry, get_database
from ..internal_utils.fallback_logger import fallback_logger


class LogsServicer(logs_service_pb2_grpc.LogsServiceServicer):
    """GRPC servicer for handling OTLP log export requests."""
    
    def __init__(self, broadcast_queue=None):
        self.db = get_database()
        self.broadcast_queue = broadcast_queue
    
    def Export(self, request: logs_service_pb2.ExportLogsServiceRequest, context) -> logs_service_pb2.ExportLogsServiceResponse:
        """Handle log export requests from OTLP exporters."""
        try:
            fallback_logger.info(f"receibed logs")
            logs_processed = 0
            
            for resource_logs in request.resource_logs:
                # Extract service name from resource attributes
                service_name = self._extract_service_name(resource_logs.resource)
                
                print(f"🔥 GRPC COLLECTOR: Service name: {service_name}")
                
                for scope_logs in resource_logs.scope_logs:
                    print(f"🔥 GRPC COLLECTOR: Processing scope with {len(scope_logs.log_records)} log records")
                    for log_record in scope_logs.log_records:
                        # Convert protobuf log record to our LogEntry
                        log_entry = self._protobuf_to_log_entry(log_record, service_name)
                        print(f"🔥 GRPC COLLECTOR: Log entry ID {log_entry.id}: {log_entry.message}")
                        
                        # Store in database
                        self.db.insert_log(log_entry)
                        
                        # Queue log for WebSocket broadcast if available
                        if self.broadcast_queue:
                            fallback_logger.info(f"🔥 GRPC: Queuing log ID {log_entry.id} for WebSocket broadcast: {log_entry.message[:50]}...")
                            try:
                                self.broadcast_queue.put_nowait(log_entry)
                                fallback_logger.info(f"🔥 GRPC: Log ID {log_entry.id} queued successfully for WebSocket broadcast")
                            except Exception as e:
                                fallback_logger.warning(f"🔥 GRPC: Failed to queue log ID {log_entry.id} for broadcast: {e}")
                        else:
                            fallback_logger.warning(f"🔥 GRPC: No broadcast queue available")
                        
                        logs_processed += 1
            
            fallback_logger.debug(f"Processed {logs_processed} log records via GRPC")
            
            return logs_service_pb2.ExportLogsServiceResponse(
                partial_success=logs_service_pb2.ExportLogsPartialSuccess()
            )
            
        except Exception as e:
            fallback_logger.error(f"Error processing OTLP logs: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return logs_service_pb2.ExportLogsServiceResponse()
    
    def _extract_service_name(self, resource: resource_pb2.Resource) -> str:
        """Extract service name from resource attributes."""
        service_name = "unknown"
        
        for attribute in resource.attributes:
            if attribute.key == "service.name":
                if attribute.value.string_value:
                    service_name = attribute.value.string_value
                break
        
        return service_name
    
    def _protobuf_to_log_entry(self, log_record: logs_pb2.LogRecord, service_name: str) -> LogEntry:
        """Convert protobuf LogRecord to our LogEntry format."""
        # Convert timestamp from nanoseconds
        timestamp = log_record.time_unix_nano or int(time.time() * 1_000_000_000)
        
        # Extract message
        message = ""
        if log_record.body.string_value:
            message = log_record.body.string_value
        elif log_record.body.int_value:
            message = str(log_record.body.int_value)
        elif log_record.body.double_value:
            message = str(log_record.body.double_value)
        elif log_record.body.bool_value:
            message = str(log_record.body.bool_value)
        else:
            message = str(log_record.body)
        
        # Convert severity to level string
        level = self._severity_to_level(log_record.severity_number)
        
        # Extract trace and span IDs
        trace_id = None
        span_id = None
        if log_record.trace_id:
            trace_id = log_record.trace_id.hex()
        if log_record.span_id:
            span_id = log_record.span_id.hex()
        
        # Extract attributes
        attributes = self._extract_attributes(log_record.attributes)
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            service=service_name,
            attributes=attributes,
            trace_id=trace_id,
            span_id=span_id
        )
    
    def _severity_to_level(self, severity_number: int) -> str:
        """Convert OpenTelemetry severity number to log level string."""
        if severity_number <= 4:  # TRACE
            return "DEBUG"
        elif severity_number <= 8:  # DEBUG  
            return "DEBUG"
        elif severity_number <= 12:  # INFO
            return "INFO"
        elif severity_number <= 16:  # WARN
            return "WARNING"
        elif severity_number <= 20:  # ERROR
            return "ERROR"
        else:  # FATAL
            return "CRITICAL"
    
    def _extract_attributes(self, attributes: List[common_pb2.KeyValue]) -> Dict[str, Any]:
        """Extract attributes from protobuf KeyValue list."""
        result = {}

        
        for attr in attributes:
            key = attr.key
            value = None


        
            if attr.value.string_value:
                value = attr.value.string_value
            elif attr.value.int_value:
                value = int(attr.value.int_value)    
            elif hasattr(attr.value, "bool_value"):
                value = bool(attr.value.bool_value)
            
            elif attr.value.double_value:
                value = float(attr.value.double_value)
            elif attr.value.array_value:
                # Handle array values
                array_values = []
                for array_item in attr.value.array_value.values:
                    if array_item.string_value:
                        array_values.append(array_item.string_value)
                    elif array_item.int_value:
                        array_values.append(array_item.int_value)
                    elif array_item.double_value:
                        array_values.append(array_item.double_value)
                    elif array_item.bool_value is not None:
                        array_values.append(array_item.bool_value)
                value = array_values
            elif attr.value.kvlist_value:
                # Handle nested key-value pairs
                nested = {}
                for nested_attr in attr.value.kvlist_value.values:
                    nested_value = None
                    if nested_attr.value.string_value:
                        nested_value = nested_attr.value.string_value
                    elif nested_attr.value.int_value:
                        nested_value = nested_attr.value.int_value
                    elif nested_attr.value.double_value:
                        nested_value = nested_attr.value.double_value
                    elif nested_attr.value.bool_value is not None:
                        nested_value = nested_attr.value.bool_value
                    
                    if nested_value is not None:
                        nested[nested_attr.key] = nested_value
                value = nested
            
            if value is not None:
                result[key] = value

        
        
        return result


class GrpcCollector:
    """GRPC server for collecting OpenTelemetry logs."""
    
    def __init__(self, port: int = 4317, max_workers: int = 10, broadcast_queue=None):
        self.port = port
        self.max_workers = max_workers
        self.broadcast_queue = broadcast_queue
        self.server: Optional[grpc.Server] = None
        
    def start(self) -> None:
        """Start the GRPC server."""
        try:
            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=self.max_workers))
            logs_service_pb2_grpc.add_LogsServiceServicer_to_server(
                LogsServicer(broadcast_queue=self.broadcast_queue), self.server
            )
            
            listen_addr = f'[::]:{self.port}'
            self.server.add_insecure_port(listen_addr)
            self.server.start()
            
            fallback_logger.info(f"GRPC collector started on port {self.port}")
            
        except Exception as e:
            fallback_logger.error(f"Failed to start GRPC collector: {e}")
            raise
    
    def stop(self, grace_period: Optional[float] = 5.0) -> None:
        """Stop the GRPC server."""
        if self.server:
            fallback_logger.info("Stopping GRPC collector...")
            self.server.stop(grace_period)
            self.server = None
    
    def wait_for_termination(self) -> None:
        """Wait for the server to terminate."""
        if self.server:
            try:
                self.server.wait_for_termination()
            except KeyboardInterrupt:
                self.stop()


async def start_grpc_collector_async(port: int = 4317, max_workers: int = 10) -> GrpcCollector:
    """Start GRPC collector in async context."""
    collector = GrpcCollector(port=port, max_workers=max_workers)
    collector.start()
    return collector