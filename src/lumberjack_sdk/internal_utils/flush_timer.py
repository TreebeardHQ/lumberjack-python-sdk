
# constants.py (or in the same file, near the other defaults)
import threading
from typing import Callable, Optional

from lumberjack_sdk.internal_utils.fallback_logger import sdk_logger

DEFAULT_FLUSH_INTERVAL = 30.0          # seconds


class FlushTimerWorker(threading.Thread):
    def __init__(self, flush_callback: Callable[[], int], interval: float = DEFAULT_FLUSH_INTERVAL) -> None:
        super().__init__(daemon=True)
        self._flush_callback = flush_callback
        self._interval = interval
        self._shutdown = threading.Event()

    def run(self) -> None:
        # sleeps atomically
        while not self._shutdown.wait(self._interval):
            try:
                # Call the flush callback
                result = self._flush_callback()

            except Exception as e:                        # never kill the thread
                sdk_logger.error("flush-timer error", exc_info=e)

    def stop(self) -> None:
        self._shutdown.set()
