# Lumberjack

Lumberjack is the best logging library for local development, giving both you and Claude and Cursor first class access to your logs via a unified UI and a local MCP server. It's fully otel compatible, so when you're ready for production observability, you can use the lumberjack SDK with basically whatever tool you want.

[Local log dashboard](./docs/images/local_log_server.png)

## Why Use Lumberjack?

### 🚀 **Core Features**

- **Claude Code Integration**: Give claude access to your local logs without giving up control of your dev server
- **Local Development**: Built-in local server with beautiful web UI for development. Collect logs across multiple services running locally. Search and filter easily.
- **Complete Observability**: Automatically instruments tracing for you.
- **OpenTelemetry Native**: Built on OpenTelemetry with support for custom exporters for logs, metrics and traces.
- **Framework Support**: Native integrations for Flask, FastAPI, and Django
- **Zero-Config Tracing**: Automatic trace context propagation across your application
- **Local-only mode and fully secure**: In production, the SDK is a no-op unless configured to export data. No data is ever sent to a remote server that you don't explicitly configure.

## Get Started

### 1. Installation

**Recommended: Using uv (fastest)**

```bash
# Basic installation with local development server
uv add 'lumberjack_sdk[local-server]'
```

**Using pip**

```bash
# Basic installation
pip install lumberjack_sdk

# With local development server
pip install 'lumberjack_sdk[local-server]'
```

### 2. Quick Setup

#### Easiest: AI-Powered Instrumentation

The fastest way to get started is to let Claude Code automatically instrument your application:

```bash
# 1. Install Lumberjack with local server support
uv add 'lumberjack_sdk[local-server]'

# 2. Run the setup command (installs MCP integration + instruments your app)
uv run lumberjack claude init
# or: lumberjack claude init (if installed with pip)
# This will:
# - Set up Claude Code MCP integration
# - Prompt to automatically instrument your application
# - Add Lumberjack SDK to your code with proper configuration
```

After running `lumberjack claude init`, Claude Code will:

- 🔍 **Analyze your codebase** to detect Flask, FastAPI, Django, or vanilla Python
- 📝 **Add Lumberjack initialization** to the right file with proper configuration
- 🏗️ **Add framework instrumentation** if applicable
- 📦 **Update your dependencies** (requirements.txt, pyproject.toml, etc.)

> [!NOTE]
> You must add `LUMBERJACK_LOCAL_SERVERED_ENABLED=true` to your local environment (dotenv or whatever) for logs to be forwarded by the SDK.

Then simply:

```bash
# Start the local development server
uv run lumberjack serve
# or: lumberjack serve (if installed with pip)

# Run your application - logs will appear in the web UI.
```

> [!TIP]
> You can just leave this server running in a tab. The SDK will auto-discover it locally. Also, if you forget, Claude can start it for you

#### Manual Setup for Local Development

If you prefer manual setup:

```bash
# 1. Start the local development server
uv run lumberjack serve
# or: lumberjack serve (if installed with pip)

# 2. Add to your Python app
```

```python
import os
from lumberjack_sdk import Lumberjack, Log

# Initialize for local development
Lumberjack.init(
    project_name="my-awesome-app",
    # Local server auto-discovery - no endpoint needed!
)


try:
    # Your application logic
    result = some_function()
    Log.info("Operation completed", result=result)
except Exception as e:
    Log.error("Operation failed", error=str(e), exc_info=True)
```

## Framework Support

> 💡 **Tip**: Run `lumberjack claude init` to automatically detect your framework and add the appropriate instrumentation code below!

### Flask

```bash
# Install with Flask support
uv add 'lumberjack_sdk[flask]'
# or: pip install 'lumberjack_sdk[flask]'
```

```python
from flask import Flask
from lumberjack_sdk import Lumberjack, LumberjackFlask, Log

app = Flask(__name__)

# Initialize Lumberjack first
Lumberjack.init(project_name="my-flask-app")

# Auto-instrument Flask
LumberjackFlask.instrument(app)

@app.route('/users/<user_id>')
def get_user(user_id):
    Log.info("Getting user", user_id=user_id)
    # Automatic request tracing and logging
    return {"user_id": user_id}
```

### FastAPI

```bash
# Install with FastAPI support
uv add 'lumberjack_sdk[fastapi]'
# or: pip install 'lumberjack_sdk[fastapi]'
```

```python
from fastapi import FastAPI
from lumberjack_sdk import Lumberjack, LumberjackFastAPI, Log

app = FastAPI()

# Initialize Lumberjack first
Lumberjack.init(project_name="my-fastapi-app")

# Auto-instrument FastAPI
LumberjackFastAPI.instrument(app)

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    Log.info("Getting user", user_id=user_id)
    # Automatic request tracing and logging
    return {"user_id": user_id}
```

### Django

```bash
# Install with Django support
uv add 'lumberjack_sdk[django]'
# or: pip install 'lumberjack_sdk[django]'
```

```python
# settings.py
from lumberjack_sdk import Lumberjack, LumberjackDjango

# Initialize Lumberjack in Django settings
Lumberjack.init(
    project_name="my-django-app",
    capture_python_logger=True,  # Capture Django's built-in logging
    python_logger_name="django",  # Capture django.* loggers
)

# Instrument Django (add this after Lumberjack.init)
LumberjackDjango.instrument()
```

## OpenTelemetry Integration

Lumberjack is built on OpenTelemetry and supports **custom exporters** for complete compatibility with the OpenTelemetry ecosystem.

### Using Custom OpenTelemetry Exporters

Use any OpenTelemetry exporter directly:

```python
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from lumberjack_sdk import Lumberjack

# Custom exporters
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)

otlp_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector:4317",
    insecure=True
)

prometheus_reader = PrometheusMetricReader()

Lumberjack.init(
    project_name="my-app",
    custom_span_exporter=jaeger_exporter,  # or otlp_exporter
    custom_metrics_exporter=prometheus_reader,
)
```

### Example: OTLP Integration

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from lumberjack_sdk import Lumberjack

# Send to any OTLP-compatible collector
otlp_span_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector:4317",
    insecure=True
)

otlp_log_exporter = OTLPLogExporter(
    endpoint="http://otel-collector:4317",
    insecure=True
)

Lumberjack.init(
    project_name="my-app",
    custom_span_exporter=otlp_span_exporter,
    custom_log_exporter=otlp_log_exporter,
)
```

## Configuration Reference

### Core Configuration

```python
Lumberjack.init(
    # Basic settings
    project_name="my-app",           # Required: Service identifier
    api_key="your-api-key",          # For production use
    env="production",                # Environment tag

    # Endpoints
    endpoint="https://api.company.com/logs/batch",     # Logs endpoint
    spans_endpoint="https://api.company.com/spans/batch", # Traces endpoint
    metrics_endpoint="https://api.company.com/metrics", # Metrics endpoint

    # Local development
    local_server_enabled=True,       # Enable local server integration

    # Performance tuning
    batch_size=500,                  # Logs per batch
    batch_age=30.0,                  # Max seconds before sending
    flush_interval=30.0,             # Periodic flush interval

    # Capture settings
    capture_stdout=True,             # Capture print() statements
    capture_python_logger=True,      # Capture logging.* calls
    python_logger_level="INFO",      # Minimum level to capture
    python_logger_name=None,         # Specific logger name to capture

    # Code snippets
    code_snippet_enabled=True,       # Include code context in logs
    code_snippet_context_lines=5,    # Lines of context
    code_snippet_max_frames=20,      # Max stack frames

    # Debugging
    debug_mode=False,                # Enable debug output
    log_to_stdout=True,              # Also log to console
    stdout_log_level="INFO",         # Console log level

    # Custom exporters
    custom_log_exporter=None,        # Custom log exporter
    custom_span_exporter=None,       # Custom span exporter
    custom_metrics_exporter=None,    # Custom metrics exporter
)
```

### Environment Variables

```bash
# Lumberjack configuration variables
LUMBERJACK_API_KEY="your-api-key"
LUMBERJACK_PROJECT_NAME="my-app"
LUMBERJACK_ENDPOINT="https://api.company.com/logs/batch"
LUMBERJACK_ENV="production"
LUMBERJACK_DEBUG_MODE="false"
LUMBERJACK_LOCAL_SERVER_ENABLED="true"  # For local development
LUMBERJACK_BATCH_SIZE="500"
LUMBERJACK_BATCH_AGE="30.0"
LUMBERJACK_FLUSH_INTERVAL="30.0"
LUMBERJACK_CAPTURE_STDOUT="true"
LUMBERJACK_CAPTURE_PYTHON_LOGGER="true"
LUMBERJACK_PYTHON_LOGGER_LEVEL="INFO"
LUMBERJACK_CODE_SNIPPET_ENABLED="true"
```

## Claude Code Integration

Enhance your debugging experience with AI-powered log analysis:

```bash
# Setup Claude Code integration
uv run lumberjack claude init
# or: lumberjack claude init (if installed with pip)

# Start local server
uv run lumberjack serve
# or: lumberjack serve (if installed with pip)

# Now ask Claude Code natural language questions:
# "Show me recent error logs"
# "Find all logs with trace ID abc123"
# "What's causing the timeout errors?"
```

## Examples

Check out the [examples directory](./examples) for complete sample applications:

- [Flask Basic Example](./examples/flask_basic)
- [FastAPI Basic Example](./examples/fastapi_basic)
- [Django Basic Example](./examples/django_basic)
- [Metrics Example](./examples/metrics_example.py)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [trylumberjack.dev/docs](https://trylumberjack.dev/docs)
- **Issues**: [GitHub Issues](https://github.com/TreebeardHQ/lumberjack-python-sdk/issues)
