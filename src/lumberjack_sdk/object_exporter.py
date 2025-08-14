"""
Clean object export functionality for sending objects to the Lumberjack API.
"""
import json
import threading
import time
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

import requests

from .internal_utils.fallback_logger import sdk_logger


class ObjectSenderWorker(threading.Thread):
    """Worker thread to process sending object requests asynchronously."""

    def __init__(self, send_queue: Queue) -> None:
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
                sdk_logger.error(f"Unexpected error in object sender: {str(e)}")
            finally:
                self._send_queue.task_done()

    def stop(self) -> None:
        self._stop_event.set()


class ObjectExporter:
    """Handles exporting object registrations to the Lumberjack API."""

    def __init__(
        self,
        api_key: str,
        objects_endpoint: str,
        project_name: Optional[str] = None
    ) -> None:
        self._api_key = api_key
        self._objects_endpoint = objects_endpoint
        self._project_name = project_name
        self._send_queue: Queue = Queue()
        self._worker: Optional[ObjectSenderWorker] = None
        self._worker_started = False

    def start_worker(self) -> None:
        """Start the background worker thread if not already started."""
        if not self._worker_started:
            if not self._worker or not self._worker.is_alive():
                self._worker = ObjectSenderWorker(self._send_queue)
                self._worker.start()
                sdk_logger.info("Object exporter worker started.")
            self._worker_started = True

    def stop_worker(self) -> None:
        """Stop the background worker thread."""
        if self._worker and self._worker.is_alive():
            self._worker.stop()
            self._send_queue.put(None)  # Signal shutdown
            self._worker.join(timeout=5)
            self._worker_started = False
            sdk_logger.info("Object exporter worker stopped.")

    def send_objects_async(
        self,
        objects: List[Dict[str, Any]],
        config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Queue objects to be sent asynchronously."""
        def send_request() -> None:
            self._send_objects(objects, config_version, update_callback)

        # Start worker if needed
        if not self._worker_started:
            self.start_worker()
        
        self._send_queue.put(send_request)

    def _send_objects(
        self,
        objects: List[Dict[str, Any]],
        config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Optional[Dict[str, Any]]:
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
                sdk_logger.debug(f"Sending {len(objects)} objects to {self._objects_endpoint}")
                response = requests.post(
                    self._objects_endpoint, headers=headers, data=data)
                
                if response.ok:
                    sdk_logger.debug(f"Objects sent successfully. objects sent: {len(objects)}")
                    result = response.json()

                    # Handle updated config from server
                    if (
                        isinstance(result, dict) 
                        and update_callback
                    ):
                        updated_config = result.get('updated_config')
                        if updated_config and isinstance(updated_config, dict):
                            update_callback(updated_config)

                    # Return the result if it's a dict, otherwise return None
                    return result if isinstance(result, dict) else None
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("Error while sending objects", exc_info=e)
            
            if attempt < max_retries - 1:  # Don't sleep on last attempt
                time.sleep(delay)
        
        sdk_logger.error("All attempts to send objects failed.")
        return None