# Lumberjack Django Example

This example demonstrates how to integrate Lumberjack logging with a Django application using the simple OpenTelemetry-based instrumentation.

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

3. Run the Django development server:
   ```bash
   python manage.py runserver
   ```

## Configuration

This example uses Django settings to configure Lumberjack. Configuration is done in two places:

### Settings Configuration

In `django_basic/settings.py`:

```python
# Lumberjack configuration
LUMBERJACK_API_KEY = os.getenv("LUMBERJACK_API_KEY", "")  # Empty for fallback mode
LUMBERJACK_PROJECT_NAME = "django-basic-example"
LUMBERJACK_LOG_TO_STDOUT = True  # Enable for development
LUMBERJACK_CAPTURE_PYTHON_LOGGER = True  # Capture Django's built-in logging
LUMBERJACK_DEBUG_MODE = DEBUG  # Match Django's debug setting
```

### App Initialization

In `example_app/apps.py`:

```python
from django.apps import AppConfig
from lumberjack_sdk.lumberjack_django import LumberjackDjango

class ExampleAppConfig(AppConfig):
    name = "example_app"

    def ready(self):
        # Initialize Lumberjack using Django settings
        # LumberjackDjango.init() automatically reads settings prefixed with LUMBERJACK_
        LumberjackDjango.init()
```

## Available Endpoints

- `GET /` - Home page with basic logging
- `GET /products/` - Products list with data logging
- `GET /slow/` - Slow operation to demonstrate performance logging
- `GET /error/` - Random error endpoint to demonstrate error logging
- `GET /user/<id>/` - User profile with parameter logging
- `GET /logging-demo/` - Comprehensive logging demonstration (Lumberjack + Django logger + print)

## How It Works

This example uses OpenTelemetry-based Django instrumentation that:

- **Automatically instruments Django** - No middleware needed! OpenTelemetry's DjangoInstrumentor handles request tracing
- **Captures multiple log sources**:
  - Lumberjack `Log.*` API calls with structured data
  - Django's built-in Python logging (forwarded to Lumberjack)
  - Print statements (if stdout capture is enabled)
- **Provides beautiful fallback logging** - Colored console output when no API key is configured
- **Preserves trace context** - All logs within a request share the same trace/span IDs

## Logging Examples

The `/logging-demo/` endpoint demonstrates three types of logging:

1. **Lumberjack Log API** (structured):
   ```python
   from lumberjack_sdk.log import Log
   Log.info("User action", user_id=123, action="login")
   ```

2. **Django Logger** (forwarded):
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
curl http://localhost:8000/

# Test comprehensive logging demo
curl http://localhost:8000/logging-demo/

# Test with parameters  
curl http://localhost:8000/user/123/

# Test error handling (shows formatted stacktraces)
curl http://localhost:8000/error/

# Test slow operations
curl http://localhost:8000/slow/
```

## Fallback Mode Features

When running without an API key, you'll see beautiful colored console output:

- 🟢 **Colored log messages** by severity (INFO=green, ERROR=red, etc.)
- 🔍 **Trace context** shown as `[span_id|trace_id]` (grayed out)
- 📝 **Readable attributes** (no more `tb_rv2_*` prefixes)
- 🔴 **Formatted stacktraces** with proper indentation
- 🚫 **No span noise** - only logs are shown

Each request is automatically traced and logged with context preserved throughout the request lifecycle.
