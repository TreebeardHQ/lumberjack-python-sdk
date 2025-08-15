# 🌲 Lumberjack Local Development Server

A beautiful, real-time log viewer for local development with multi-service support and Claude Code integration.

## Quick Start

### 1. Install with local server support
```bash
pip install -e ".[local-server]"
```

### 2. Start the local server
```bash
lumberjack serve
```

This will:
- ✅ Start the log collection server on http://localhost:8080
- ✅ Auto-open your browser to the log viewer
- ✅ Start GRPC collector on port 4317
- ✅ Enable real-time log tailing by default

### 3. Enable in your application
```python
from lumberjack_sdk import Lumberjack, Log

# Enable local server in your app
Lumberjack.init(
    project_name="my-app",
    local_server_enabled=True,  # Enable local server
    debug_mode=True
)

# Your logs will now appear in the local viewer
Log.info("Application started", version="1.0.0")
Log.error("Something went wrong", error_code=500)
```

## Features

### 🎯 Multi-Service Support
- View logs from multiple local services in one place
- Filter by service name
- Each service gets its own identifier

### ⚡ Real-Time Tailing
- New logs appear instantly via WebSocket
- Automatic scrolling (pause by scrolling up)
- Beautiful shadcn/ui components

### 🔍 Search & Filter
- Full-text search across log messages
- Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Filter by service name
- Column visibility controls

### 🤖 Claude Code Integration
- Search logs directly from Claude Code
- Analyze error patterns
- Get recent logs and trace information

## Advanced Usage

### Environment Variables
```bash
# Enable local server
export LUMBERJACK_LOCAL_SERVER_ENABLED=true

# Custom endpoint (default: localhost:4317) 
export LUMBERJACK_LOCAL_SERVER_ENDPOINT=localhost:4318

# Custom service name
export LUMBERJACK_LOCAL_SERVER_SERVICE_NAME=my-api
```

### Persistent Storage
```bash
# Use persistent SQLite database
lumberjack serve --db-path ./logs.db

# Custom port
lumberjack serve --port 3000
```

### Claude Code Integration
```bash
# Setup MCP integration
lumberjack claude init

# Then restart Claude Code and use commands like:
# "Search for error logs from the api service"
# "Show me recent logs"
# "What errors happened in the last hour?"
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your App      │───▶│  Local Server    │───▶│   Web UI        │
│                 │    │                  │    │                 │
│ Lumberjack SDK  │    │ • GRPC Collector │    │ • Real-time     │
│ Local Exporter  │    │ • SQLite Storage │    │ • Search/Filter │
│                 │    │ • WebSocket API  │    │ • Multi-service │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌──────────────────┐
                       │   Claude Code    │
                       │                  │
                       │ • MCP Server     │
                       │ • Log Search     │  
                       │ • Error Analysis │
                       └──────────────────┘
```

## Development Workflow

1. **Start Local Server**: `lumberjack serve`
2. **Develop Your App**: Logs automatically appear in viewer
3. **Debug Issues**: Use search, filters, and Claude Code integration
4. **Multi-Service**: Each service shows up with its own identifier

## Configuration Options

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Enabled | `LUMBERJACK_LOCAL_SERVER_ENABLED` | `false` | Enable local server export |
| Endpoint | `LUMBERJACK_LOCAL_SERVER_ENDPOINT` | `localhost:4317` | GRPC endpoint |
| Service Name | `LUMBERJACK_LOCAL_SERVER_SERVICE_NAME` | Project name | Service identifier |

## Comparison with Production

| Feature | Local Server | Production |
|---------|-------------|------------|
| **Storage** | SQLite (in-memory/disk) | Cloud storage |
| **UI** | Local web interface | Lumberjack dashboard |
| **Real-time** | WebSocket updates | Dashboard streaming |
| **Search** | Local full-text search | Advanced analytics |
| **Claude Integration** | MCP server | API integration |

## Troubleshooting

### Port Already in Use
```bash
lumberjack serve --port 8081  # Use different port
```

### Local Server Not Available
- Ensure you've installed with `[local-server]` extras
- Check if port 4317 is available
- Verify the server is running: `curl http://localhost:8080/api/stats`

### No Logs Appearing
- Verify `local_server_enabled=True` in your config
- Check the terminal for connection errors
- Ensure your app is using the Lumberjack SDK correctly

### Claude Code Integration Issues
```bash
# Re-run setup
lumberjack claude init

# Check Claude Code config location
ls ~/.config/claude_code/claude_config.json
```

Perfect for local development, debugging, and understanding your application's behavior in real-time! 🚀