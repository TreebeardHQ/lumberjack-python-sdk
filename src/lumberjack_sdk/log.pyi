import re
from .constants import EXEC_TYPE_RESERVED_V2 as EXEC_TYPE_RESERVED_V2, EXEC_VALUE_RESERVED_V2 as EXEC_VALUE_RESERVED_V2, FILE_KEY_RESERVED_V2 as FILE_KEY_RESERVED_V2, FUNCTION_KEY_RESERVED_V2 as FUNCTION_KEY_RESERVED_V2, LINE_KEY_RESERVED_V2 as LINE_KEY_RESERVED_V2, MESSAGE_KEY_RESERVED_V2 as MESSAGE_KEY_RESERVED_V2, SOURCE_KEY_RESERVED_V2 as SOURCE_KEY_RESERVED_V2, SPAN_ID_KEY_RESERVED_V2 as SPAN_ID_KEY_RESERVED_V2, TRACEBACK_KEY_RESERVED_V2 as TRACEBACK_KEY_RESERVED_V2, TRACE_ID_KEY_RESERVED_V2 as TRACE_ID_KEY_RESERVED_V2
from .core import Lumberjack as Lumberjack
from .internal_utils.fallback_logger import sdk_logger as sdk_logger
from _typeshed import Incomplete
from typing import Any, Mapping

masked_terms: Incomplete
pattern: Incomplete

class Log:
    @staticmethod
    def debug(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def info(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def warning(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def warn(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def error(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def critical(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None: ...
    @staticmethod
    def recurse_and_collect_dict(data: Mapping[str, Any], collector: dict[str, Any], prefix: str = '') -> dict[str, Any]: ...

def mask_pw(match: re.Match[str]): ...
