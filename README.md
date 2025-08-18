# Lumberjack Python SDK

Lumberjack is a powerful Python observability library that provides comprehensive logging, tracing, and metrics collection with seamless OpenTelemetry integration. Built for modern Python applications, it offers both cloud-hosted and local development capabilities.

## Why Use Lumberjack?

### 🚀 **Core Features**

- **Complete Observability**: Logs, traces, and metrics in one unified SDK
- **OpenTelemetry Native**: Built on OpenTelemetry with support for custom exporters
- **Local Development**: Built-in local server with beautiful web UI for development
- **Framework Support**: Native integrations for Flask, FastAPI, and Django
- **Zero-Config Tracing**: Automatic trace context propagation across your application
- **Intelligent Batching**: Efficient log forwarding with configurable batching strategies
- **Claude Code Integration**: AI-powered log analysis and debugging with MCP integration

### 🎯 **Perfect For**

- **Local Development**: Rich debugging experience with instant log visualization
- **Production Monitoring**: Scalable log forwarding to any backend with custom exporters
- **Microservices**: Distributed tracing across service boundaries
- **AI-Assisted Debugging**: Query and analyze logs with Claude Code

## Get Started

### Installation

```bash
# Basic installation
pip install lumberjack_sdk

# With local development server
pip install 'lumberjack_sdk[local-server]'
```

### Quick Setup

#### Easiest: AI-Powered Instrumentation

The fastest way to get started is to let Claude Code automatically instrument your application:

```bash
# 1. Install Lumberjack with local server support
pip install 'lumberjack_sdk[local-server]'

# 2. Run the setup command (installs MCP integration + instruments your app)
lumberjack claude init
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

Then simply:
```bash
# Start the local development server  
lumberjack serve

# Run your application - logs will appear in the web UI
```

#### Manual Setup for Local Development

If you prefer manual setup:

```bash
# 1. Start the local development server
lumberjack serve

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

# Start logging
Log.info("Application started", version="1.0.0")
Log.debug("Debug info", user_count=42)

try:
    # Your application logic
    result = some_function()
    Log.info("Operation completed", result=result)
except Exception as e:
    Log.error("Operation failed", error=str(e), exc_info=True)
```

#### For Production

```python
from lumberjack_sdk import Lumberjack, Log

# Initialize for production
Lumberjack.init(
    project_name="my-awesome-app",
    api_key=os.environ["LUMBERJACK_API_KEY"],
    endpoint="https://api.trylumberjack.com/logs/batch",
    env="production"
)

Log.info("Production app started")
```

## Framework Support

> 💡 **Tip**: Run `lumberjack claude init` to automatically detect your framework and add the appropriate instrumentation code below!

### Flask

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

## Advanced Features

### Distributed Tracing

```python
from lumberjack_sdk import start_span, Log

# Manual span creation
with start_span("payment_processing") as span:
    Log.info("Processing payment", amount=100)
    
    with start_span("validate_card") as child_span:
        Log.debug("Validating card")
        # span context automatically propagated
        
    Log.info("Payment completed")
```

### Metrics Collection

```python
from lumberjack_sdk import create_counter, create_histogram

# Create metrics
request_counter = create_counter(
    "http_requests_total",
    description="Total HTTP requests"
)

response_time = create_histogram(
    "http_request_duration_seconds",
    description="HTTP request duration"
)

# Use metrics
request_counter.add(1, {"method": "GET", "route": "/users"})
response_time.record(0.142, {"method": "GET", "status": "200"})
```

### Error Tracking

```python
from lumberjack_sdk import Log

try:
    risky_operation()
except Exception as e:
    # Automatic exception capture with stack traces
    Log.error("Operation failed", 
              exc_info=True,  # Captures full stack trace
              user_id="123",
              operation="data_processing")
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
    objects_endpoint="https://api.company.com/objects/register", # Objects endpoint
    
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
lumberjack claude init

# Start local server
lumberjack serve

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

- **Documentation**: [docs.lumberjack.dev](https://docs.lumberjack.dev)
- **Issues**: [GitHub Issues](https://github.com/trylumberjack/lumberjack-python-sdk/issues)
- **Community**: [Discord](https://discord.gg/lumberjack)