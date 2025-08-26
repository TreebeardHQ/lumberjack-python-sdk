from .constants import ERROR_KEY_RESERVED_V2 as ERROR_KEY_RESERVED_V2, EXEC_TYPE_RESERVED_V2 as EXEC_TYPE_RESERVED_V2, EXEC_VALUE_RESERVED_V2 as EXEC_VALUE_RESERVED_V2, FILE_KEY_RESERVED_V2 as FILE_KEY_RESERVED_V2, FUNCTION_KEY_RESERVED_V2 as FUNCTION_KEY_RESERVED_V2, LEVEL_KEY_RESERVED_V2 as LEVEL_KEY_RESERVED_V2, LINE_KEY_RESERVED_V2 as LINE_KEY_RESERVED_V2, LOGGER_NAME_KEY_RESERVED_V2 as LOGGER_NAME_KEY_RESERVED_V2, MESSAGE_KEY_RESERVED_V2 as MESSAGE_KEY_RESERVED_V2, SOURCE_KEY_RESERVED_V2 as SOURCE_KEY_RESERVED_V2, SPAN_ID_KEY_RESERVED_V2 as SPAN_ID_KEY_RESERVED_V2, TRACEBACK_KEY_RESERVED_V2 as TRACEBACK_KEY_RESERVED_V2, TRACE_ID_KEY_RESERVED_V2 as TRACE_ID_KEY_RESERVED_V2, TRACE_NAME_KEY_RESERVED_V2 as TRACE_NAME_KEY_RESERVED_V2, TS_KEY_RESERVED_V2 as TS_KEY_RESERVED_V2
from .internal_utils.fallback_logger import fallback_logger as fallback_logger
from opentelemetry.sdk._logs import LogData as LogData
from opentelemetry.sdk._logs.export import LogExportResult, LogExporter
from typing import Sequence

class FallbackLogExporter(LogExporter):
    def export(self, batch: Sequence[LogData]) -> LogExportResult: ...
    def shutdown(self) -> None: ...
    def force_flush(self, timeout_millis: int = 30000) -> bool: ...
