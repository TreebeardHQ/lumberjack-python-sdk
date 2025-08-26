"""
Service discovery and TTL management for Lumberjack local server.

Handles:
- Writing/reading server configuration to ~/.lumberjack.config
- TTL validation with heartbeat updates
- Single server instance validation
- Process existence checking
"""
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

from ..internal_utils.fallback_logger import fallback_logger


class ServerConfig:
    """Represents server configuration with TTL validation."""
    
    def __init__(
        self,
        server_url: str,
        grpc_port: int,
        pid: int,
        ttl_seconds: int = 300,
        last_heartbeat: Optional[float] = None
    ):
        self.server_url = server_url
        self.grpc_port = grpc_port
        self.pid = pid
        self.ttl_seconds = ttl_seconds
        self.last_heartbeat = last_heartbeat or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "server_url": self.server_url,
            "grpc_port": self.grpc_port,
            "last_heartbeat": self.last_heartbeat,
            "ttl_seconds": self.ttl_seconds,
            "pid": self.pid
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerConfig":
        """Create from dictionary."""
        return cls(
            server_url=data["server_url"],
            grpc_port=data["grpc_port"],
            pid=data["pid"],
            ttl_seconds=data.get("ttl_seconds", 300),
            last_heartbeat=data.get("last_heartbeat", time.time())
        )
    
    def is_alive(self) -> bool:
        """Check if server is alive based on TTL and process existence."""
        current_time = time.time()
        
        # Check TTL
        if current_time - self.last_heartbeat > self.ttl_seconds:
            time_since_heartbeat = current_time - self.last_heartbeat
            fallback_logger.debug(
                f"Server config expired (TTL: {self.ttl_seconds}s, "
                f"last heartbeat: {time_since_heartbeat:.1f}s ago)"
            )
            return False
        
        # Check if process still exists
        try:
            if psutil.pid_exists(self.pid):
                # Additional check: verify it's actually our server process
                proc = psutil.Process(self.pid)
                if proc.is_running():
                    return True
                else:
                    fallback_logger.debug(f"Process {self.pid} exists but is not running")
                    return False
            else:
                fallback_logger.debug(f"Process {self.pid} no longer exists")
                return False
        except psutil.NoSuchProcess:
            fallback_logger.debug(f"Process {self.pid} no longer exists")
            return False
        except Exception as e:
            fallback_logger.warning(f"Error checking process {self.pid}: {e}")
            return False
    
    def time_since_heartbeat(self) -> float:
        """Get time since last heartbeat in seconds."""
        return time.time() - self.last_heartbeat


class ServiceDiscovery:
    """Manages service discovery for Lumberjack local server."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize service discovery.
        
        Args:
            config_path: Custom path to config file (default: ~/.lumberjack.config)
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path.home() / ".lumberjack.config"
    
    def check_existing_server(self) -> Optional[ServerConfig]:
        """
        Check if another server instance is already running.
        
        Returns:
            ServerConfig if running server found, None otherwise
        """
        try:
            config = self.read_server_config()
            if config and config.is_alive():
                return config
            elif config:
                # Config exists but server is dead, clean it up
                fallback_logger.debug("Found stale server config, cleaning up")
                self.cleanup_stale_config()
            return None
        except Exception as e:
            fallback_logger.debug(f"Error checking existing server: {e}")
            return None
    
    def write_server_config(
        self,
        server_url: str,
        grpc_port: int,
        ttl_seconds: int = 300
    ) -> None:
        """
        Write server configuration to config file.
        
        Args:
            server_url: Server URL (e.g., "127.0.0.1:8080")
            grpc_port: GRPC port for log collection
            ttl_seconds: TTL for the configuration
        """
        config = ServerConfig(
            server_url=server_url,
            grpc_port=grpc_port,
            pid=os.getpid(),
            ttl_seconds=ttl_seconds
        )
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            fallback_logger.info(f"Server config written to {self.config_path}")
            fallback_logger.debug(f"Server details: {config.to_dict()}")
            
        except Exception as e:
            fallback_logger.error(f"Failed to write server config: {e}")
            raise
    
    def read_server_config(self) -> Optional[ServerConfig]:
        """
        Read server configuration from config file.
        
        Returns:
            ServerConfig if valid config exists, None otherwise
        """
        try:
            if not self.config_path.exists():
                fallback_logger.debug(f"No server config file found at {self.config_path}")
                return None
            
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            config = ServerConfig.from_dict(data)
            fallback_logger.debug(f"Read server config: {config.to_dict()}")
            return config
            
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            fallback_logger.warning(f"Invalid or corrupted server config: {e}")
            return None
        except Exception as e:
            fallback_logger.error(f"Error reading server config: {e}")
            return None
    
    def update_heartbeat(self) -> bool:
        """
        Update the heartbeat timestamp in the config file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.read_server_config()
            if not config:
                fallback_logger.warning("Cannot update heartbeat - no config found")
                return False
            
            # Verify this is our process
            current_pid = os.getpid()
            if config.pid != current_pid:
                fallback_logger.warning(
                    f"Config PID {config.pid} doesn't match current process {current_pid}"
                )
                return False
            
            # Update heartbeat
            config.last_heartbeat = time.time()
            
            with open(self.config_path, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            fallback_logger.debug("Heartbeat updated")
            return True
            
        except Exception as e:
            fallback_logger.error(f"Failed to update heartbeat: {e}")
            return False
    
    def cleanup_stale_config(self) -> None:
        """Remove stale configuration file."""
        try:
            if self.config_path.exists():
                self.config_path.unlink()
                fallback_logger.debug(f"Removed stale config file: {self.config_path}")
        except Exception as e:
            fallback_logger.warning(f"Failed to remove stale config: {e}")
    
    def cleanup_own_config(self) -> None:
        """Remove configuration file if it belongs to current process."""
        try:
            config = self.read_server_config()
            if config and config.pid == os.getpid():
                self.config_path.unlink()
                fallback_logger.info(f"Cleaned up own config file: {self.config_path}")
            else:
                fallback_logger.debug("Config file doesn't belong to current process, not removing")
        except Exception as e:
            fallback_logger.warning(f"Failed to cleanup own config: {e}")
    
    def is_server_available(self) -> tuple[bool, Optional[ServerConfig]]:
        """
        Check if a server is available.
        
        Returns:
            Tuple of (is_available, config)
        """
        config = self.read_server_config()
        if config and config.is_alive():
            return True, config
        return False, None
    
    def get_server_endpoint(self) -> Optional[str]:
        """
        Get the GRPC endpoint for the server.
        
        Returns:
            GRPC endpoint string or None if no server available
        """
        is_available, config = self.is_server_available()
        if is_available and config:
            # Extract host from server_url
            if ':' in config.server_url:
                host = config.server_url.split(':')[0]
            else:
                host = config.server_url
            return f"{host}:{config.grpc_port}"
        return None


# Global service discovery instance
_service_discovery: Optional[ServiceDiscovery] = None


def get_service_discovery() -> ServiceDiscovery:
    """Get global service discovery instance."""
    global _service_discovery
    if _service_discovery is None:
        _service_discovery = ServiceDiscovery()
    return _service_discovery


def check_existing_server() -> Optional[ServerConfig]:
    """Check if another server instance is already running."""
    return get_service_discovery().check_existing_server()


def write_server_config(server_url: str, grpc_port: int, ttl_seconds: int = 300) -> None:
    """Write server configuration to config file."""
    get_service_discovery().write_server_config(server_url, grpc_port, ttl_seconds)


def update_heartbeat() -> bool:
    """Update the heartbeat timestamp."""
    return get_service_discovery().update_heartbeat()


def cleanup_own_config() -> None:
    """Clean up configuration file for current process."""
    get_service_discovery().cleanup_own_config()


def is_server_available() -> tuple[bool, Optional[ServerConfig]]:
    """Check if a server is available."""
    return get_service_discovery().is_server_available()


def get_server_endpoint() -> Optional[str]:
    """Get the GRPC endpoint for the server."""
    return get_service_discovery().get_server_endpoint()


def is_port_available(port: int, host: str = "localhost") -> bool:
    """
    Check if a port is available for binding.
    
    Args:
        port: Port number to check
        host: Host to check (default: localhost)
        
    Returns:
        True if port is available, False if in use
    """
    # Test both localhost and all interfaces (0.0.0.0)
    hosts_to_test = [host]
    if host == "localhost":
        hosts_to_test.extend(["127.0.0.1", "0.0.0.0"])
    
    for test_host in hosts_to_test:
        try:
            # Try to bind to the port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((test_host, port))
                # Successfully bound to this host, continue testing others
        except OSError:
            # Failed to bind to this host, port is in use
            return False
    
    return True


def check_port_availability(port: int, host: str = "localhost") -> Optional[str]:
    """
    Check if a port is available and provide details about what's using it.
    
    Args:
        port: Port number to check
        host: Host to check
        
    Returns:
        None if port is available, error message if port is in use
    """
    if is_port_available(port, host):
        return None
    
    # Port is in use, try to find what's using it
    try:
        import subprocess
        result = subprocess.run(['lsof', '-i', f':{port}'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Skip header line
                # Parse the first process using the port
                process_line = lines[1].split()
                if len(process_line) >= 2:
                    command = process_line[0]
                    pid = process_line[1]
                    return f"Port {port} is in use by {command} (PID: {pid})"
        
        # Fallback if lsof parsing fails
        return f"Port {port} is in use by another process"
        
    except Exception:
        # If lsof fails, just return generic message
        return f"Port {port} is in use by another process"