"""
FastAPI server for Lumberjack Local Development Server.

Provides REST API, WebSocket streaming, and static file serving
for the log viewer interface.
"""
import asyncio
import json
import os
import webbrowser
import queue
import threading
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .database import get_database, LogEntry
from .grpc_collector import GrpcCollector
from .service_discovery import check_existing_server, write_server_config, update_heartbeat, cleanup_own_config, check_port_availability
from ..internal_utils.fallback_logger import fallback_logger


class ConnectionManager:
    """Manages WebSocket connections for real-time log streaming."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        fallback_logger.debug(f"WebSocket connected. Active connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        fallback_logger.debug(f"WebSocket disconnected. Active connections: {len(self.active_connections)}")
    
    async def broadcast_log(self, log_entry: LogEntry):
        """Broadcast a new log entry to all connected clients."""
        fallback_logger.info(f"🔥 WEBSOCKET: Broadcasting log ID {log_entry.id} to {len(self.active_connections)} connections: {log_entry.message[:50]}...")
        if not self.active_connections:
            fallback_logger.warning(f"🔥 WEBSOCKET: No active connections to broadcast to")
            return
        
        message = json.dumps({
            "type": "new_log",
            "data": log_entry.to_dict()
        })
        
        # Send to all connections, removing any that fail
        failed_connections = set()
        
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                fallback_logger.debug(f"Failed to send to WebSocket: {e}")
                failed_connections.add(connection)
        
        # Remove failed connections
        self.active_connections -= failed_connections
    
    async def send_initial_logs(self, websocket: WebSocket, limit: int = 50):
        """Send recent logs to a newly connected client."""
        try:
            db = get_database()
            recent_logs = db.get_recent_logs(limit=limit)
            
            message = json.dumps({
                "type": "initial_logs",
                "data": [log.to_dict() for log in recent_logs]
            })
            
            await websocket.send_text(message)
        except Exception as e:
            fallback_logger.error(f"Failed to send initial logs: {e}")


# Global connection manager and GRPC collector
connection_manager = ConnectionManager()
grpc_collector: Optional[GrpcCollector] = None

# Queue for cross-thread communication between GRPC and WebSocket
log_broadcast_queue: queue.Queue = queue.Queue()

# Heartbeat management
heartbeat_task: Optional[asyncio.Task] = None
server_host: str = "127.0.0.1"
server_port: int = 8080

async def process_log_broadcast_queue():
    """Background task to process log broadcasts from GRPC thread."""
    while True:
        try:
            # Check for logs in the queue (non-blocking)
            try:
                log_entry = log_broadcast_queue.get_nowait()
                fallback_logger.info(f"🔥 QUEUE: Processing log ID {log_entry.id} from broadcast queue")
                await connection_manager.broadcast_log(log_entry)
                log_broadcast_queue.task_done()
            except queue.Empty:
                # No logs to process, wait a bit
                await asyncio.sleep(0.1)
        except Exception as e:
            fallback_logger.error(f"Error processing log broadcast queue: {e}")
            await asyncio.sleep(1)


async def heartbeat_worker():
    """Background task to update server heartbeat every 60 seconds."""
    while True:
        try:
            await asyncio.sleep(60)  # Update every 60 seconds
            success = update_heartbeat()
            if success:
                fallback_logger.debug("Heartbeat updated successfully")
            else:
                fallback_logger.warning("Failed to update heartbeat")
        except asyncio.CancelledError:
            fallback_logger.debug("Heartbeat worker cancelled")
            break
        except Exception as e:
            fallback_logger.error(f"Error in heartbeat worker: {e}")
            await asyncio.sleep(60)  # Continue trying


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    # Startup
    global grpc_collector, heartbeat_task
    
    # Check if another server instance is already running
    existing_server = check_existing_server()
    if existing_server:
        fallback_logger.error(f"Another Lumberjack server is already running!")
        fallback_logger.error(f"  PID: {existing_server.pid}")
        fallback_logger.error(f"  Server URL: {existing_server.server_url}")
        fallback_logger.error(f"  GRPC Port: {existing_server.grpc_port}")
        fallback_logger.error(f"  Last heartbeat: {existing_server.time_since_heartbeat():.1f}s ago")
        fallback_logger.error("Shutting down to prevent conflicts.")
        sys.exit(1)
    
    # Check if GRPC port 4317 is available
    port_error = check_port_availability(4317)
    if port_error:
        fallback_logger.error(f"Cannot start GRPC collector: {port_error}")
        fallback_logger.error("Please stop the process using port 4317 or use a different port.")
        sys.exit(1)
    
    try:
        # Write server configuration
        server_url = f"{server_host}:{server_port}"
        write_server_config(server_url, 4317)
        fallback_logger.info(f"Server config written for {server_url}")
        
        # Start GRPC collector with queue for cross-thread communication
        grpc_collector = GrpcCollector(port=4317, broadcast_queue=log_broadcast_queue)
        grpc_collector.start()
        
        # Start background task to process log broadcasts
        broadcast_task = asyncio.create_task(process_log_broadcast_queue())
        
        # Start heartbeat worker
        heartbeat_task = asyncio.create_task(heartbeat_worker())
        
        fallback_logger.info("Local development server started successfully")
        
        yield
        
    finally:
        # Shutdown
        try:
            # Cancel heartbeat task
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Stop GRPC collector
            if grpc_collector:
                grpc_collector.stop()
            
            # Clean up server config
            cleanup_own_config()
            
        except Exception as e:
            fallback_logger.error(f"Error during shutdown: {e}")
        
        fallback_logger.info("Local development server stopped")


# Create FastAPI app
app = FastAPI(
    title="Lumberjack Local Development Server",
    description="Local log collection and viewing for development",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for real-time log streaming."""
    await connection_manager.connect(websocket)
    
    try:
        # Send initial recent logs
        await connection_manager.send_initial_logs(websocket)
        
        # Keep connection alive and handle any messages
        while True:
            try:
                # We don't expect messages from client, but need to keep connection alive
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send a ping to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        fallback_logger.error(f"WebSocket error: {e}")
    finally:
        connection_manager.disconnect(websocket)


@app.get("/api/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    since_timestamp: Optional[int] = Query(None)
):
    """Get logs with optional filtering and pagination."""
    try:
        db = get_database()
        logs = db.get_logs(
            limit=limit,
            offset=offset,
            service=service,
            level=level,
            search_query=search,
            since_timestamp=since_timestamp
        )
        
        total_count = db.get_log_count(
            service=service,
            level=level,
            since_timestamp=since_timestamp
        )
        
        return {
            "logs": [log.to_dict() for log in logs],
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(logs)) < total_count
        }
        
    except Exception as e:
        fallback_logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/services")
async def get_services():
    """Get list of all services that have sent logs."""
    try:
        db = get_database()
        services = db.get_services()
        return {"services": services}
        
    except Exception as e:
        fallback_logger.error(f"Error getting services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get basic statistics about logs."""
    try:
        db = get_database()
        
        total_logs = db.get_log_count()
        services = db.get_services()
        
        # Get counts by level
        level_counts = {}
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            level_counts[level.lower()] = db.get_log_count(level=level)
        
        # Get counts by service
        service_counts = {}
        for service in services:
            service_counts[service] = db.get_log_count(service=service)
        
        return {
            "total_logs": total_logs,
            "services_count": len(services),
            "services": services,
            "level_counts": level_counts,
            "service_counts": service_counts
        }
        
    except Exception as e:
        fallback_logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/logs/new")
async def new_log_notification(log_entry: dict):
    """Endpoint for notifying about new logs (used internally by GRPC collector)."""
    try:
        # Convert dict back to LogEntry for broadcasting
        entry = LogEntry(
            id=log_entry.get("id"),
            timestamp=log_entry.get("timestamp", 0),
            level=log_entry.get("level", "INFO"),
            message=log_entry.get("message", ""),
            service=log_entry.get("service", "unknown"),
            attributes=log_entry.get("attributes", {}),
            trace_id=log_entry.get("trace_id"),
            span_id=log_entry.get("span_id")
        )

        print("broadcasting via endpoint")
        
        # Broadcast to WebSocket clients
        await connection_manager.broadcast_log(entry)
        
        return {"status": "broadcasted"}
        
    except Exception as e:
        fallback_logger.error(f"Error broadcasting new log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Static file serving
def get_static_dir() -> Path:
    """Get the static files directory."""
    current_dir = Path(__file__).parent
    static_dir = current_dir / "static"
    
    # If static files don't exist, create a minimal index.html
    if not static_dir.exists():
        static_dir.mkdir(exist_ok=True)
        
    index_file = static_dir / "index.html"
    if not index_file.exists():
        # Create a minimal HTML page if React bundle doesn't exist yet
        minimal_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lumberjack Local Server</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
               padding: 2rem; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; 
                    padding: 2rem; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; margin-bottom: 1rem; }
        .status { padding: 1rem; background: #e3f2fd; border-radius: 4px; margin: 1rem 0; }
        pre { background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌲 Lumberjack Local Development Server</h1>
        <div class="status">
            <strong>Status:</strong> Server is running and ready to collect logs!
        </div>
        <p>The React UI is not yet built. To build it:</p>
        <pre>cd ui && npm install && npm run build</pre>
        
        <h2>API Endpoints</h2>
        <ul>
            <li><a href="/api/logs">/api/logs</a> - Get logs</li>
            <li><a href="/api/services">/api/services</a> - Get services</li>
            <li><a href="/api/stats">/api/stats</a> - Get statistics</li>
        </ul>
        
        <h2>GRPC Collector</h2>
        <p>GRPC collector is running on port 4317 for OTLP log collection.</p>
    </div>
    
    <script>
        // Simple WebSocket test
        const ws = new WebSocket(`ws://${window.location.host}/ws/logs`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'new_log') {
                console.log('New log received:', data.data);
            }
        };
    </script>
</body>
</html>
        """
        with open(index_file, 'w') as f:
            f.write(minimal_html)
    
    return static_dir


# Mount static files
static_dir = get_static_dir()
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Also mount assets directory for direct access (HTML expects /assets paths)
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main index.html file."""
    index_path = static_dir / "index.html"
    return FileResponse(index_path)


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon if available."""
    favicon_path = static_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        raise HTTPException(status_code=404)


def start_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    db_path: Optional[str] = None,
    open_browser: bool = True,
    log_level: str = "info"
) -> None:
    """
    Start the local development server.
    
    Args:
        host: Host to bind to
        port: Port to serve on
        db_path: Path to SQLite database file
        open_browser: Whether to open browser automatically
        log_level: Uvicorn log level
    """
    # Set global variables for use in lifespan function
    global server_host, server_port
    server_host = host
    server_port = port
    
    # Initialize database with custom path if provided
    if db_path:
        get_database(db_path)
        fallback_logger.info(f"Using database: {db_path}")
    else:
        get_database()  # Use in-memory database
        fallback_logger.info("Using in-memory database")
    
    # Open browser if requested
    if open_browser:
        def open_browser_delayed():
            import time
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open(f"http://{host}:{port}")
        
        import threading
        threading.Thread(target=open_browser_delayed, daemon=True).start()
    
    # Start the server
    fallback_logger.info(f"Starting Lumberjack Local Server on http://{host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,  # Reduce noise
    )