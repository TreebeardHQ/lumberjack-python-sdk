from _typeshed import Incomplete
from typing import TypedDict

class FrameInfo(TypedDict):
    filename: str
    lineno: int
    function: str
    code_snippet: list[str]
    context_line_numbers: list[int]
    error_line_index: int
    locals: dict[str, str] | None

class CodeSnippetExtractor:
    context_lines: Incomplete
    max_frames: Incomplete
    capture_locals: Incomplete
    exclude_patterns: Incomplete
    def __init__(self, context_lines: int = 5, max_frames: int = 50, capture_locals: bool = False, exclude_patterns: list[str] | None = None) -> None: ...
    def extract_from_exception(self, exception: Exception) -> list[FrameInfo]: ...

def format_code_snippet(frame_info: FrameInfo, show_line_numbers: bool = True, highlight_error: bool = True) -> str: ...
