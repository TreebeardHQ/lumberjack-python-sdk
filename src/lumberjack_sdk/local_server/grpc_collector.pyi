import grpc
from ..internal_utils.fallback_logger import fallback_logger as fallback_logger
from .database import LogEntry as LogEntry, get_database as get_database
from _typeshed import Incomplete
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2, logs_service_pb2_grpc
from opentelemetry.proto.common.v1 import common_pb2 as common_pb2
from opentelemetry.proto.logs.v1 import logs_pb2 as logs_pb2
from opentelemetry.proto.resource.v1 import resource_pb2 as resource_pb2

class LogsServicer(logs_service_pb2_grpc.LogsServiceServicer):
    db: Incomplete
    broadcast_queue: Incomplete
    def __init__(self, broadcast_queue: Incomplete | None = None) -> None: ...
    def Export(self, request: logs_service_pb2.ExportLogsServiceRequest, context) -> logs_service_pb2.ExportLogsServiceResponse: ...

class GrpcCollector:
    port: Incomplete
    max_workers: Incomplete
    broadcast_queue: Incomplete
    server: grpc.Server | None
    def __init__(self, port: int = 4317, max_workers: int = 10, broadcast_queue: Incomplete | None = None) -> None: ...
    def start(self) -> None: ...
    def stop(self, grace_period: float | None = 5.0) -> None: ...
    def wait_for_termination(self) -> None: ...

async def start_grpc_collector_async(port: int = 4317, max_workers: int = 10) -> GrpcCollector: ...
