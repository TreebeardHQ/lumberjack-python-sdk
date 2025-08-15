"""
Local server exporter for Lumberjack SDK.

Exports logs to the local development server via GRPC with retry logic.
"""
import random
import time
from typing import Optional, Sequence, Dict, Any

import grpc
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs.export import LogExporter, LogExportResult
from opentelemetry.sdk._logs import LogData
from opentelemetry.sdk.resources import Resource

from ..internal_utils.fallback_logger import fallback_logger


class LocalServerLogExporter(LogExporter):
    """
    Log exporter that sends logs to the local Lumberjack development server.
    
    Features exponential backoff retry logic and graceful fallback when
    the local server is unavailable.
    """
    
    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        service_name: Optional[str] = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        timeout: float = 10.0
    ):
        """
        Initialize the local server exporter.
        
        Args:
            endpoint: GRPC endpoint of local server
            service_name: Name of the service (for multi-service support)
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff delay in seconds
            max_backoff: Maximum backoff delay in seconds
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint
        self.service_name = service_name or "default"
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.timeout = timeout
        
        # Use the OTLP GRPC exporter as the underlying implementation
        self._otlp_exporter: Optional[OTLPLogExporter] = None
        self._last_failure_time = 0.0
        self._consecutive_failures = 0
        self._is_available = True
        
        self._initialize_exporter()
    
    def _initialize_exporter(self) -> None:
        """Initialize the underlying OTLP exporter."""
        try:
            # Configure headers to include service name
            headers = {}
            if self.service_name:
                headers["service-name"] = self.service_name
            
            # Convert HTTP endpoint to GRPC format for OTLP
            grpc_endpoint = self.endpoint.replace("http://", "").replace("https://", "")
            
            self._otlp_exporter = OTLPLogExporter(
                endpoint=grpc_endpoint,
                insecure=True,  # For local development
                timeout=self.timeout,
                headers=headers
            )
            fallback_logger.info(f"Initialized local server exporter for {self.service_name} at endpint {grpc_endpoint}")
            
        except Exception as e:
            fallback_logger.warning(f"Failed to initialize local server exporter: {e}")
            self._otlp_exporter = None
    
    def export(self, batch: Sequence[LogData]) -> LogExportResult:
        """
        Export logs with retry logic.
        
        Args:
            batch: Sequence of LogData to export
            
        Returns:
            LogExportResult indicating success or failure
        """
        if not self._is_available or not self._otlp_exporter:
            return self._handle_unavailable()
        
        # Try to export with retries
        for attempt in range(self.max_retries + 1):
            try:
               
                
                result = self._otlp_exporter.export(batch)
                
                if result == LogExportResult.SUCCESS:
                    # Reset failure tracking on success
                    self._consecutive_failures = 0
                    self._is_available = True
                    fallback_logger.debug(f"Successfully exported {len(batch)} logs to local server")
                    return result
                else:
                    fallback_logger.warning(f"Local server export failed with result: {result}")
                    
            except grpc.RpcError as e:
                self._handle_grpc_error(e, attempt)
                if attempt < self.max_retries:
                    self._wait_with_backoff(attempt)
                    
            except Exception as e:
                fallback_logger.error(f"Unexpected error exporting to local server: {e}", exc_info=e)
                self._consecutive_failures += 1
                if attempt < self.max_retries:
                    self._wait_with_backoff(attempt)
        
        # All retries failed
        return self._handle_export_failure()
    
    def _handle_grpc_error(self, error: grpc.RpcError, attempt: int) -> None:
        """Handle GRPC-specific errors."""
        status_code = error.code()
        
        if status_code == grpc.StatusCode.UNAVAILABLE:
            fallback_logger.debug(f"Local server unavailable (attempt {attempt + 1})")
        elif status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
            fallback_logger.warning(f"Local server timeout (attempt {attempt + 1})")
        else:
            fallback_logger.warning(f"GRPC error: {status_code} - {error.details()} (attempt {attempt + 1})")
        
        self._consecutive_failures += 1
    
    def _wait_with_backoff(self, attempt: int) -> None:
        """Wait with exponential backoff plus jitter."""
        backoff = min(
            self.initial_backoff * (2 ** attempt),
            self.max_backoff
        )
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.1, 0.3) * backoff
        wait_time = backoff + jitter
        
        fallback_logger.debug(f"Waiting {wait_time:.2f}s before retry")
        time.sleep(wait_time)
    
    def _handle_export_failure(self) -> LogExportResult:
        """Handle export failure after all retries."""
        self._last_failure_time = time.time()
        
        # If we've had too many consecutive failures, mark as unavailable temporarily
        if self._consecutive_failures >= 5:
            self._is_available = False
            fallback_logger.warning(
                f"Local server marked unavailable after {self._consecutive_failures} failures"
            )
        
        return LogExportResult.FAILURE
    
    def _handle_unavailable(self) -> LogExportResult:
        """Handle when local server is marked as unavailable."""
        current_time = time.time()
        
        # Try to re-enable after a cooldown period
        cooldown_period = min(300, 30 + (self._consecutive_failures * 10))  # Max 5 minutes
        
        if current_time - self._last_failure_time > cooldown_period:
            self._is_available = True
            self._consecutive_failures = 0
            fallback_logger.debug("Re-enabling local server exporter after cooldown")
            
            # Try to reinitialize the exporter
            self._initialize_exporter()
            
            # If we have an exporter now, try to export
            if self._otlp_exporter:
                return LogExportResult.SUCCESS  # Will be retried
        
        # Still in cooldown or no exporter available
        fallback_logger.debug("Local server exporter unavailable, skipping export")
        return LogExportResult.SUCCESS  # Don't block the pipeline
    
    def shutdown(self) -> None:
        """Shutdown the exporter."""
        if self._otlp_exporter:
            try:
                self._otlp_exporter.shutdown()
            except Exception as e:
                fallback_logger.warning(f"Error shutting down local server exporter: {e}")
            finally:
                self._otlp_exporter = None
    
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending logs."""
        if self._otlp_exporter:
            try:
                return self._otlp_exporter.force_flush(timeout_millis)
            except Exception as e:
                fallback_logger.warning(f"Error force flushing local server exporter: {e}")
                return False
        return True
    
    @property
    def is_available(self) -> bool:
        """Check if the local server is currently available."""
        return self._is_available and self._otlp_exporter is not None


def create_local_server_exporter(
    endpoint: str = "http://localhost:4317",
    service_name: Optional[str] = None,
    **kwargs: Any
) -> LocalServerLogExporter:
    """
    Create a local server log exporter with default configuration.
    
    Args:
        endpoint: Local server GRPC endpoint
        service_name: Service name for multi-service support
        **kwargs: Additional configuration options
        
    Returns:
        Configured LocalServerLogExporter instance
    """
    return LocalServerLogExporter(
        endpoint=endpoint,
        service_name=service_name,
        **kwargs
    )


def is_local_server_available(endpoint: str = "http://localhost:4317", timeout: float = 2.0) -> bool:
    """
    Check if the local server is available by attempting a connection.
    
    Args:
        endpoint: Server endpoint to check
        timeout: Connection timeout in seconds
        
    Returns:
        True if server is available, False otherwise
    """
    try:
        # Extract host and port from endpoint
        if "://" in endpoint:
            endpoint = endpoint.split("://", 1)[1]
        
        host, port = endpoint.split(":", 1)
        port = int(port)
        
        # Try to connect
        channel = grpc.insecure_channel(f"{host}:{port}")
        try:
            grpc.channel_ready_future(channel).result(timeout=timeout)
            return True
        finally:
            channel.close()
            
    except Exception as e:
        fallback_logger.debug(f"Local server not available at {endpoint}: {e}")
        return False