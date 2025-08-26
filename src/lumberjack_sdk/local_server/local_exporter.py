"""
Local server exporter for Lumberjack SDK with service discovery and log caching.

Features:
- Service discovery via ~/.lumberjack.config
- Local log caching with FIFO eviction (max 200 logs)
- Periodic server discovery and cache flushing
- TTL validation and process checking
"""
import threading
import time
from collections import deque
from typing import Any, Dict, Optional, Sequence

from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LogData
from opentelemetry.sdk._logs.export import LogExporter, LogExportResult

from ..internal_utils.fallback_logger import fallback_logger
from .service_discovery import get_server_endpoint, get_service_discovery, is_server_available


class LocalServerLogExporter(LogExporter):
    """
    Log exporter that uses service discovery to find local Lumberjack server.
    
    Features:
    - Service discovery with TTL validation
    - Local log caching (max 200 logs) with FIFO eviction
    - Periodic server discovery and cache flushing
    - No hardcoded endpoint fallback - only connects when server is available
    """
    
    def __init__(
        self,
        service_name: Optional[str] = None,
        cache_max_size: int = 200,
        discovery_interval: float = 30.0,
        timeout: float = 10.0
    ):
        """
        Initialize the local server exporter with service discovery.
        
        Args:
            service_name: Name of the service (for multi-service support)
            cache_max_size: Maximum number of logs to cache
            discovery_interval: Interval to check for server availability (seconds)
            timeout: Request timeout in seconds
        """
        self.service_name = service_name or "default"
        self.cache_max_size = cache_max_size
        self.discovery_interval = discovery_interval
        self.timeout = timeout
        
        # Service discovery
        self.service_discovery = get_service_discovery()
        
        # Log caching with FIFO eviction
        self._log_cache: deque[LogData] = deque(maxlen=cache_max_size)
        self._cache_lock = threading.Lock()
        self._cache_stats = {
            'cached_count': 0,
            'flushed_count': 0,
            'evicted_count': 0,
            'failed_flush_count': 0
        }
        
        # Server connection state
        self._otlp_exporter: Optional[OTLPLogExporter] = None
        self._current_endpoint: Optional[str] = None
        self._last_discovery_time = 0.0
        self._server_available = False
        
        # Background discovery thread
        self._discovery_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Initialize and start discovery
        self._try_discover_server()
        self._start_discovery_thread()
        
        fallback_logger.info(f"Local server exporter initialized for service: {self.service_name}")
        fallback_logger.info(
            f"Cache settings: max_size={cache_max_size}, discovery_interval={discovery_interval}s"
        )
    
    def _start_discovery_thread(self) -> None:
        """Start background thread for periodic server discovery."""
        if self._discovery_thread is None or not self._discovery_thread.is_alive():
            self._discovery_thread = threading.Thread(
                target=self._discovery_worker,
                daemon=True,
                name="LocalServerDiscovery"
            )
            self._discovery_thread.start()
            fallback_logger.debug("Started server discovery thread")
    
    def _discovery_worker(self) -> None:
        """Background worker for periodic server discovery and cache flushing."""
        while not self._shutdown_event.wait(self.discovery_interval):
            try:
                self._try_discover_server()
                if self._server_available:
                    self._flush_cache()
            except Exception as e:
                fallback_logger.error(f"Error in discovery worker: {e}")
    
    def _try_discover_server(self) -> bool:
        """
        Try to discover server via service discovery.
        
        Returns:
            True if server found and available, False otherwise
        """
        current_time = time.time()
        
        # Rate limit discovery attempts
        if current_time - self._last_discovery_time < 5.0:
            return self._server_available
        
        self._last_discovery_time = current_time
        
        try:
            endpoint = get_server_endpoint()
            
            if endpoint:
                # Server found, check if endpoint changed
                if endpoint != self._current_endpoint:
                    fallback_logger.info(f"Discovered server at: {endpoint}")
                    self._current_endpoint = endpoint
                    self._initialize_exporter(endpoint)
                
                if self._otlp_exporter:
                    self._server_available = True
                    return True
            else:
                # No server available
                if self._server_available:
                    fallback_logger.debug("Server no longer available")
                self._server_available = False
                self._current_endpoint = None
                self._otlp_exporter = None
                
        except Exception as e:
            fallback_logger.debug(f"Error during server discovery: {e}")
            self._server_available = False
            
        return self._server_available
    
    def _initialize_exporter(self, endpoint: str) -> None:
        """Initialize OTLP exporter for the discovered endpoint."""
        try:
            # Configure headers to include service name
            headers = {}
            if self.service_name:
                headers["service-name"] = self.service_name
            
            fallback_logger.debug(f"Attempting to initialize OTLP exporter for {endpoint}")
            self._otlp_exporter = OTLPLogExporter(
                endpoint=endpoint,
                insecure=True,  # For local development
                timeout=self.timeout,
                headers=headers
            )
            fallback_logger.info(f"✅ Successfully initialized OTLP exporter for {endpoint}")
            
        except Exception as e:
            fallback_logger.error(f"❌ Failed to initialize OTLP exporter for {endpoint}: {e}")
            import traceback
            fallback_logger.error(f"Traceback: {traceback.format_exc()}")
            self._otlp_exporter = None
    
    def export(self, batch: Sequence[LogData]) -> LogExportResult:
        """
        Export logs to server or cache locally.
        
        Args:
            batch: Sequence of LogData to export
            
        Returns:
            LogExportResult.SUCCESS (we handle failures gracefully)
        """
        # Try to discover server if not recently checked
        if not self._server_available:
            self._try_discover_server()
        
        # Try to export if server is available
        if self._server_available and self._otlp_exporter:
            try:
                fallback_logger.debug(f"Attempting to export {len(batch)} logs to server via OTLP...")
                result = self._otlp_exporter.export(batch)
                if result == LogExportResult.SUCCESS:
                    
                    # Successful export, try to flush cache
                    self._flush_cache()
                    return LogExportResult.SUCCESS
                else:
                    fallback_logger.warning(f"❌ Server export failed with result: {result}")
                    
            except Exception as e:
                fallback_logger.error(f"❌ Error exporting to server: {e}")
                import traceback
                fallback_logger.error(f"Traceback: {traceback.format_exc()}")
                # Mark server as unavailable for next discovery cycle
                self._server_available = False
        
        # Server not available or export failed, cache the logs
        self._cache_logs(batch)
        
        # Always return success to not block the logging pipeline
        return LogExportResult.SUCCESS
    
    def _cache_logs(self, batch: Sequence[LogData]) -> None:
        """Cache logs locally with FIFO eviction."""
        with self._cache_lock:
            initial_cache_size = len(self._log_cache)
            
            for log_data in batch:
                # deque automatically evicts oldest when maxlen is reached
                if len(self._log_cache) == self.cache_max_size:
                    self._cache_stats['evicted_count'] += 1
                
                self._log_cache.append(log_data)
                self._cache_stats['cached_count'] += 1
            
            evicted = max(0, initial_cache_size + len(batch) - len(self._log_cache))
            
            if len(batch) > 0:
                cache_size = len(self._log_cache)
                if not self._server_available:
                    fallback_logger.debug(
                        f"Cached {len(batch)} logs (cache: {cache_size}/{self.cache_max_size}, "
                        f"evicted: {evicted}) - server not available"
                    )
                else:
                    fallback_logger.debug(
                        f"Cached {len(batch)} logs after server export failed "
                        f"(cache: {cache_size}/{self.cache_max_size}, evicted: {evicted})"
                    )
    
    def _flush_cache(self) -> bool:
        """
        Flush cached logs to the server.
        
        Returns:
            True if cache was flushed successfully, False otherwise
        """
        if not self._server_available or not self._otlp_exporter:
            return False
        
        with self._cache_lock:
            if not self._log_cache:
                return True  # Nothing to flush
            
            # Convert cache to list for export
            cached_logs = list(self._log_cache)
            cache_size = len(cached_logs)
        
        try:
            result = self._otlp_exporter.export(cached_logs)
            
            if result == LogExportResult.SUCCESS:
                with self._cache_lock:
                    # Only clear logs that were successfully sent
                    # (in case new logs were added during export)
                    for _ in range(min(cache_size, len(self._log_cache))):
                        self._log_cache.popleft()
                    self._cache_stats['flushed_count'] += cache_size
                
                fallback_logger.info(f"Flushed {cache_size} cached logs to server")
                return True
            else:
                fallback_logger.warning(f"Failed to flush cache: {result}")
                self._cache_stats['failed_flush_count'] += 1
                
        except Exception as e:
            fallback_logger.warning(f"Error flushing cache: {e}")
            self._cache_stats['failed_flush_count'] += 1
            # Mark server as unavailable for next discovery cycle
            self._server_available = False
        
        return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            stats = self._cache_stats.copy()
            stats['current_cache_size'] = len(self._log_cache)
            stats['cache_max_size'] = self.cache_max_size
            stats['server_available'] = self._server_available
            stats['current_endpoint'] = self._current_endpoint
        return stats
    
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        Force flush any pending logs.
        
        Args:
            timeout_millis: Timeout in milliseconds
            
        Returns:
            True if successful, False otherwise
        """
        # Try to discover server first
        if not self._server_available:
            self._try_discover_server()
        
        # Attempt to flush cache
        if self._server_available:
            success = self._flush_cache()
            if success:
                fallback_logger.debug("Force flush completed successfully")
                return True
        
        # If server not available, logs remain cached
        cache_size = len(self._log_cache)
        if cache_size > 0:
            fallback_logger.warning(
                f"Force flush incomplete - {cache_size} logs remain cached (server not available)"
            )
        
        return cache_size == 0
    
    def shutdown(self) -> None:
        """Shutdown the exporter and cleanup resources."""
        fallback_logger.debug("Shutting down local server exporter")
        
        # Signal shutdown to discovery thread
        self._shutdown_event.set()
        
        # Wait for discovery thread to stop
        if self._discovery_thread and self._discovery_thread.is_alive():
            self._discovery_thread.join(timeout=5.0)
            if self._discovery_thread.is_alive():
                fallback_logger.warning("Discovery thread did not stop gracefully")
        
        # Try final flush
        if self._server_available:
            self._flush_cache()
        
        # Shutdown OTLP exporter
        if self._otlp_exporter:
            try:
                self._otlp_exporter.shutdown()
            except Exception as e:
                fallback_logger.warning(f"Error shutting down OTLP exporter: {e}")
            finally:
                self._otlp_exporter = None
        
        # Log final cache stats
        stats = self.get_cache_stats()
        fallback_logger.info(f"Final cache stats: {stats}")
        
        fallback_logger.debug("Local server exporter shutdown complete")


def create_local_server_exporter(
    service_name: Optional[str] = None,
    **kwargs: Any
) -> LocalServerLogExporter:
    """
    Create a local server log exporter with service discovery.
    
    Args:
        service_name: Service name for multi-service support
        **kwargs: Additional configuration options
        
    Returns:
        Configured LocalServerLogExporter instance
    """
    return LocalServerLogExporter(
        service_name=service_name,
        **kwargs
    )


def is_local_server_available() -> bool:
    """
    Check if the local server is available via service discovery.
    
    Returns:
        True if server is available, False otherwise
    """
    available, _ = is_server_available()
    return available