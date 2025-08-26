"""
MCP server for Lumberjack Local Development Server.

Provides simple tools for Claude Code to search and view logs.
"""
import subprocess
import sys
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

try:
    from mcp.server.fastmcp import FastMCP
    import requests
except ImportError as e:
    print(f"MCP dependencies not installed. Install with: pip install 'lumberjack_sdk[local-server]'")
    print(f"Import error details: {e}")
    sys.exit(1)

from ..internal_utils.fallback_logger import fallback_logger

def truncate_value(value: Any, max_length: int = 1000) -> str:
    """Truncate long values to prevent overwhelming output."""
    str_value = str(value)
    if len(str_value) > max_length:
        return str_value[:max_length] + "... (truncated)"
    return str_value

# Initialize MCP server
mcp = FastMCP("Lumberjack Local Server")

# Default local server URL
LOCAL_SERVER_URL = "http://127.0.0.1:8080"

def call_local_server(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call the local server API and return the response."""
    try:
        url = f"{LOCAL_SERVER_URL}{endpoint}"
        response = requests.get(url, params=params or {}, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Server returned status {response.status_code}: {response.text}"}
    
    except requests.exceptions.ConnectionError:
        return {"error": "Unable to connect to local server. Is 'lumberjack serve' running?"}
    except requests.exceptions.Timeout:
        return {"error": "Request to local server timed out"}
    except Exception as e:
        return {"error": f"Failed to call local server: {str(e)}"}


@mcp.tool()
def recent_logs(
    limit: int = 50,
    service: Optional[str] = None,
    level: Optional[str] = None
) -> str:
    """
    Get recent logs.
    
    Args:
        limit: Number of logs to return (default: 50, max: 200)
        service: Filter by service name (optional)
        level: Filter by log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (optional)
    
    Returns:
        Formatted log entries
    """
    limit = min(limit, 200)
    
    # Build parameters for API call
    params = {"limit": limit}
    if service:
        params["service"] = service
    if level:
        params["level"] = level
    
    # Call the local server API
    response = call_local_server("/api/logs", params)
    
    if "error" in response:
        return f"Error: {response['error']}"
    
    logs = response.get("logs", [])
    if not logs:
        return "No logs found."
    
    # Format as readable text with all attributes
    output = []
    for log in logs:
        timestamp = datetime.fromtimestamp(log["timestamp"] / 1_000_000_000)
        time_str = timestamp.strftime("%H:%M:%S.%f")[:-3]
        
        # Base log line
        lines = [f"[{time_str}] {log['level']:8} {log['service']:15} {log['message']}"]
        
        # Add trace information if present
        if log.get("trace_id"):
            lines.append(f"  Trace ID = {log['trace_id']}")
        if log.get("span_id"):
            lines.append(f"  Span ID = {log['span_id']}")
        
        # Add all custom attributes (excluding internal and redundant attributes)
        if log.get("attributes"):
            # Filter out tb_rv2_* attributes and redundant otel IDs (already shown above)
            filtered_attrs = {
                k: v for k, v in log["attributes"].items() 
                if not k.startswith("tb_rv2_") and k not in ["otelSpanID", "otelTraceID"]
            }
            
            if filtered_attrs:
                lines.append("  Attributes:")
                for key, value in filtered_attrs.items():
                    # Don't truncate exception-related fields (stack traces, etc.)
                    exception_fields = ['exception', 'stack', 'trace', 'traceback', 'error', 'stacktrace']
                    should_truncate = not any(field in key.lower() for field in exception_fields)
                    
                    if should_truncate:
                        display_value = truncate_value(value, 1000)
                    else:
                        display_value = str(value)
                        
                    lines.append(f"    {key} = {display_value}")
        
        output.append("\n".join(lines))
    
    return "\n\n".join(output)


@mcp.tool()
def search_logs(
    query: str,
    service: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 50
) -> str:
    """
    Search logs by message content or trace ID.
    
    Args:
        query: Search term to find in log messages or trace ID (supports partial matches)
        service: Filter by service name (optional)
        level: Filter by log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (optional)
        limit: Number of logs to return (default: 50, max: 200)
    
    Returns:
        Formatted matching log entries
    """
    limit = min(limit, 200)
    
    # Build parameters for API call
    params = {"limit": limit}
    if service:
        params["service"] = service
    if level:
        params["level"] = level
    
    params["search"] = query
    
    # Call the local server API
    response = call_local_server("/api/logs", params)
    
    if "error" in response:
        return f"Error: {response['error']}"
    
    logs = response.get("logs", [])
    
    # Check if this might be a trace_id search (hex string pattern)
    # and do additional filtering if needed
    import re
    is_trace_search = bool(re.match(r'^[a-fA-F0-9]+$', query)) and len(query) >= 6
    
    if is_trace_search:
        # Filter logs by trace_id for better accuracy
        filtered_logs = []
        for log in logs:
            if log.get("trace_id") and query.lower() in log["trace_id"].lower():
                filtered_logs.append(log)
        
        # If we found trace matches, use them; otherwise keep original results
        if filtered_logs:
            logs = filtered_logs[:limit]
            search_term = f"trace ID containing '{query}'"
        else:
            search_term = f"'{query}'"
    else:
        search_term = f"'{query}'"
    
    if not logs:
        return f"No logs found matching {search_term}"
    
    # Format as readable text with all attributes
    output = [f"Found {len(logs)} logs matching {search_term}:\n"]
    for log in logs:
        timestamp = datetime.fromtimestamp(log["timestamp"] / 1_000_000_000)
        time_str = timestamp.strftime("%H:%M:%S.%f")[:-3]
        
        # Base log line
        lines = [f"[{time_str}] {log['level']:8} {log['service']:15} {log['message']}"]
        
        # Add trace information if present
        if log.get("trace_id"):
            lines.append(f"  Trace ID = {log['trace_id']}")
        if log.get("span_id"):
            lines.append(f"  Span ID = {log['span_id']}")
        
        # Add all custom attributes (excluding internal and redundant attributes)
        if log.get("attributes"):
            # Filter out tb_rv2_* attributes and redundant otel IDs (already shown above)
            filtered_attrs = {
                k: v for k, v in log["attributes"].items() 
                if not k.startswith("tb_rv2_") and k not in ["otelSpanID", "otelTraceID"]
            }
            
            if filtered_attrs:
                lines.append("  Attributes:")
                for key, value in filtered_attrs.items():
                    # Don't truncate exception-related fields (stack traces, etc.)
                    exception_fields = ['exception', 'stack', 'trace', 'traceback', 'error', 'stacktrace']
                    should_truncate = not any(field in key.lower() for field in exception_fields)
                    
                    if should_truncate:
                        display_value = truncate_value(value, 1000)
                    else:
                        display_value = str(value)
                        
                    lines.append(f"    {key} = {display_value}")
        
        output.append("\n".join(lines))
    
    return "\n\n".join(output)


@mcp.tool()
def list_services() -> str:
    """
    List all services that have sent logs, with counts.
    
    Returns:
        List of services with log counts
    """
    # Call the local server API for services
    services_response = call_local_server("/api/services")
    
    if "error" in services_response:
        return f"Error: {services_response['error']}"
    
    services = services_response.get("services", [])
    
    if not services:
        return "No services found."
    
    # Call the stats API to get detailed counts
    stats_response = call_local_server("/api/stats")
    
    output = ["Services with logs:\n"]
    
    if "error" not in stats_response:
        service_counts = stats_response.get("service_counts", {})
        level_counts = stats_response.get("level_counts", {})
        
        for service in services:
            total = service_counts.get(service, 0)
            
            # Get error and warning counts for this service (approximate)
            # Note: The API doesn't provide per-service level counts, so we'll show overall stats
            output.append(f"  {service:20} Total: {total:6} logs")
        
        # Add overall error/warning stats
        total_errors = level_counts.get("error", 0)
        total_warnings = level_counts.get("warning", 0)
        output.append(f"\nOverall: {total_errors} errors, {total_warnings} warnings across all services")
    else:
        # Fallback if stats API fails
        for service in services:
            output.append(f"  {service}")
    
    return "\n".join(output)


@mcp.tool()
def start_server(
    port: Optional[int] = None,
    open_browser: bool = False
) -> str:
    """
    Start the Lumberjack local development server.
    
    Args:
        port: Port to serve on (optional, auto-detect if not provided)
        open_browser: Whether to open browser automatically (default: False)
    
    Returns:
        Server status message
    """
    try:
        # Build command
        cmd = ["lumberjack", "serve"]
        
        if port:
            cmd.extend(["--port", str(port)])
        
        if not open_browser:
            cmd.append("--no-browser")
        
        # Start server in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment to see if it starts successfully
        import time
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is None:
            port_msg = f"port {port}" if port else "auto-detected port"
            return f"✅ Lumberjack server started on {port_msg}\n" \
                   f"Web UI: http://127.0.0.1:{port if port else 8080}\n" \
                   f"GRPC Collector: localhost:4317"
        else:
            stdout, stderr = process.communicate()
            return f"❌ Failed to start server:\n{stderr}"
            
    except FileNotFoundError:
        return "❌ lumberjack command not found. Install with: pip install 'lumberjack_sdk[local-server]'"
    except Exception as e:
        return f"❌ Error starting server: {str(e)}"


# Main entry point for running the MCP server
def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()