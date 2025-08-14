# Lumberjack FastAPI Example

This example demonstrates how to integrate Lumberjack logging with a FastAPI application using the simple OpenTelemetry-based instrumentation.

## Setup

1. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Set your Lumberjack API key as an environment variable:

   ```bash
   export LUMBERJACK_API_KEY="your-api-key-here"
   ```
   
   If no API key is provided, the app will run in fallback mode with colored console logging.

3. Run the FastAPI development server:
   ```bash
   python app.py
   ```
   
   Or use uvicorn directly:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8002 --reload
   ```

## Configuration

The FastAPI example is configured directly in the app code:

```python
from lumberjack_sdk import Lumberjack, LumberjackFastAPI

# Initialize Lumberjack
Lumberjack.init(
    api_key="",  # Empty for fallback mode
    project_name="fastapi-basic-example",
    log_to_stdout=True,  # Enable for development
    capture_python_logger=True,  # Capture FastAPI's built-in logging
    capture_stdout=True,  # Capture print statements
    debug_mode=True
)

# Instrument FastAPI with Lumberjack
LumberjackFastAPI.instrument(app)
```

## Available Endpoints

- `GET /` - Home page with basic logging
- `GET /products` - Products list with query parameters (`category`, `min_price`)
- `GET /products/{id}` - Get single product by ID  
- `GET /slow` - Slow async operation to demonstrate performance logging
- `GET /error` - Random error endpoint to demonstrate error logging
- `GET /logging-demo` - Comprehensive logging demonstration (Lumberjack + FastAPI logger + print)
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

## How It Works

This example uses OpenTelemetry-based FastAPI instrumentation that:

- **Automatically instruments FastAPI** - No middleware needed! OpenTelemetry's FastAPIInstrumentor handles request tracing
- **Captures multiple log sources**:
  - Lumberjack `Log.*` API calls with structured data
  - FastAPI's built-in Python logging (forwarded to Lumberjack)
  - Print statements (if stdout capture is enabled)
- **Provides beautiful fallback logging** - Colored console output when no API key is configured
- **Preserves trace context** - All logs within a request share the same trace/span IDs
- **Async-friendly** - Works perfectly with FastAPI's async/await patterns

## Logging Examples

The `/logging-demo` endpoint demonstrates three types of logging:

1. **Lumberjack Log API** (structured):
   ```python
   from lumberjack_sdk.log import Log
   Log.info("User action", user_id=123, action="login")
   ```

2. **FastAPI Logger** (forwarded):
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info("Standard Python logging message")
   ```

3. **Print Statements** (captured):
   ```python
   print("Debug output from print statement")
   ```

## Example Usage

```bash
# Test basic functionality
curl http://localhost:8002/

# Test comprehensive logging demo
curl http://localhost:8002/logging-demo

# Test with query parameters
curl "http://localhost:8002/products?category=electronics&min_price=50"

# Test single product
curl http://localhost:8002/products/42

# Test error handling (shows formatted stacktraces)
curl http://localhost:8002/error

# Test async operations
curl http://localhost:8002/slow

# Interactive API docs
open http://localhost:8002/docs
```

## FastAPI Features Demonstrated

- **Path Parameters**: `/products/{product_id}`
- **Query Parameters**: `/products?category=electronics&min_price=50`
- **Request Objects**: Access to headers, method, URL in `/logging-demo`
- **Exception Handling**: Global exception handler with logging
- **Async Operations**: Async endpoints with proper logging
- **Dependency Injection**: FastAPI's natural request handling
- **Automatic OpenAPI**: Generated documentation at `/docs`

## Fallback Mode Features

When running without an API key, you'll see beautiful colored console output:

- 🟢 **Colored log messages** by severity (INFO=green, ERROR=red, etc.)
- 🔍 **Trace context** shown as `[span_id|trace_id]` (grayed out)
- 📝 **Readable attributes** (no more `tb_rv2_*` prefixes)
- 🔴 **Formatted stacktraces** with proper indentation
- 🚫 **No span noise** - only logs are shown

Each request is automatically traced and logged with context preserved throughout the entire async request lifecycle.

## Performance Notes

The OpenTelemetry FastAPI instrumentation is designed to work efficiently with:
- Async/await patterns
- High-concurrency applications
- Minimal performance overhead
- Automatic cleanup of trace contexts

Perfect for production FastAPI applications that need comprehensive logging and tracing!