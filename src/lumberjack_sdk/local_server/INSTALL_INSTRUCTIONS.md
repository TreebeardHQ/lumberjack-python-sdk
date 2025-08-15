# Lumberjack SDK Installation Instructions

## Your Task
You need to instrument this Python application with the Lumberjack SDK for local log collection. Follow these instructions carefully to make the necessary code changes.

## Overview
The Lumberjack SDK sends logs to a local GRPC collector on port 4317 for development purposes. You will be configuring it with **local_server_enabled=True** which means:
- No API key is needed (use empty string: `api_key=""`)
- Logs are sent to localhost:4317
- The user will view logs at http://localhost:8080

## Step 1: Check for Existing Lumberjack Installation

**IMPORTANT**: Before making changes, search the codebase for existing Lumberjack usage:

1. Search for `from lumberjack_sdk` or `import lumberjack_sdk`
2. Search for `Lumberjack.init(` or `LumberjackFlask` or `LumberjackFastAPI` or `LumberjackDjango`
3. Search for `LUMBERJACK_` in settings files

**If Lumberjack is already installed:**
- **DO NOT** change existing configuration parameters
- **ONLY** ensure `local_server_enabled=True` is set (or `LUMBERJACK_LOCAL_SERVER_ENABLED=True` for Django)
- **DO NOT** modify `project_name`, `api_key`, or other existing settings
- Skip to Step 4 (Verification)

**If Lumberjack is NOT installed, continue with Step 2.**

## Step 2: Detect the Web Framework
Search the codebase to determine which framework is being used:

1. **Flask**: Search for `from flask import Flask` or `Flask(__name__)` 
2. **FastAPI**: Search for `from fastapi import FastAPI` or `FastAPI()`
3. **Django**: Search for `django` in requirements.txt or settings.py files
4. **None**: If none of the above are found, treat it as a standalone Python application

## Step 3: Add the SDK to Dependencies

Find the appropriate dependency file and add the Lumberjack SDK with the correct extras based on the framework:

**For Flask applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk[local-server,flask]`
- If `pyproject.toml` exists: `"lumberjack-sdk[local-server,flask]"`
- If `setup.py` exists: `'lumberjack-sdk[local-server,flask]'`

**For FastAPI applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk[local-server,fastapi]`
- If `pyproject.toml` exists: `"lumberjack-sdk[local-server,fastapi]"`
- If `setup.py` exists: `'lumberjack-sdk[local-server,fastapi]'`

**For Django applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk[local-server,django]`
- If `pyproject.toml` exists: `"lumberjack-sdk[local-server,django]"`
- If `setup.py` exists: `'lumberjack-sdk[local-server,django]'`

**For standalone Python applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk[local-server]`
- If `pyproject.toml` exists: `"lumberjack-sdk[local-server]"`
- If `setup.py` exists: `'lumberjack-sdk[local-server]'`

## Step 4: Add the Initialization Code

Based on the framework detected in Step 2, add the appropriate initialization code:

### For Flask Applications

In your main Flask app file (usually `app.py` or `__init__.py`):

```python
from flask import Flask
from lumberjack_sdk import Lumberjack, LumberjackFlask

app = Flask(__name__)

# Initialize Lumberjack for local development
Lumberjack.init(
    project_name="my-flask-app",  # Replace with your project name
    api_key="",  # Empty string for local mode
    local_server_enabled=True,  # Enable local server mode
    log_to_stdout=True,  # Also show logs in terminal
    capture_python_logger=True,  # Capture Flask's built-in logging
    debug_mode=False  # Set to True only if you need verbose SDK logging
)

# Instrument Flask app
LumberjackFlask.instrument(app)
```

### For FastAPI Applications

In your main FastAPI app file (usually `main.py` or `app.py`):

```python
from fastapi import FastAPI
from lumberjack_sdk import Lumberjack, LumberjackFastAPI

app = FastAPI()

# Initialize Lumberjack for local development
Lumberjack.init(
    project_name="my-fastapi-app",  # Replace with your project name
    api_key="",  # Empty string for local mode
    local_server_enabled=True,  # Enable local server mode
    log_to_stdout=True,  # Also show logs in terminal
    capture_python_logger=True,  # Capture FastAPI's built-in logging
    debug_mode=False  # Set to True only if you need verbose SDK logging
)

# Instrument FastAPI app
LumberjackFastAPI.instrument(app)
```

### For Django Applications

**Step 1:** Add to your Django settings file (usually `settings.py`):

```python
import os

# Add Lumberjack configuration settings
LUMBERJACK_PROJECT_NAME = "my-django-app"  # Replace with your project name
LUMBERJACK_API_KEY = ""  # Empty string for local mode
LUMBERJACK_LOG_TO_STDOUT = True  # Also show logs in terminal
LUMBERJACK_CAPTURE_PYTHON_LOGGER = True  # Capture Django's built-in logging
LUMBERJACK_DEBUG_MODE = False  # Set to True only if you need verbose SDK logging
```

**Step 2:** In any Django app's `apps.py` file (create one if needed):

```python
from django.apps import AppConfig

class YourAppConfig(AppConfig):
    name = "your_app_name"
    
    def ready(self):
        """Initialize Lumberjack when Django starts up."""
        from lumberjack_sdk.lumberjack_django import LumberjackDjango
        
        # Initialize Lumberjack using Django settings
        LumberjackDjango.init()
```

**Step 3:** Make sure your app is in INSTALLED_APPS in settings.py:

```python
INSTALLED_APPS = [
    # ... other apps
    "your_app_name.apps.YourAppConfig",
]
```

### For Standalone Python Applications

At the top of your main Python file:

```python
import logging
from lumberjack_sdk import Lumberjack

# Initialize Lumberjack for local development
Lumberjack.init(
    project_name="my-python-app",  # Replace with your project name
    api_key="",  # Empty string for local mode
    local_server_enabled=True,  # Enable local server mode
    log_to_stdout=True,  # Also show logs in terminal
    capture_python_logger=True,  # Capture all Python logging
    debug_mode=False  # Set to True only if you need verbose SDK logging
)

# Now all Python logging will be captured
logger = logging.getLogger(__name__)
logger.info("Application started with Lumberjack logging")
```

## Step 5: Verify Installation

After adding the initialization code:

1. Start the Lumberjack local server:
   ```bash
   lumberjack serve
   ```

2. Run your application

3. Check that logs appear in the web UI at http://localhost:8080

## Important Configuration Notes

- **api_key=""**: Empty string enables fallback mode for local development
- **local_server_enabled=True**: Sends logs to localhost:4317 for local viewing
- **project_name**: Use a descriptive name for your project/service
- **log_to_stdout=True**: Shows logs in terminal for immediate feedback
- **capture_python_logger=True**: Captures all Python logging framework messages
- **debug_mode=False**: Set to True only if you need verbose SDK internal logging

## Additional Features

### Custom Attributes
You can add environment variables or pass additional parameters to `Lumberjack.init()`:
```python
Lumberjack.init(
    project_name="my-app",
    api_key="",
    local_server_enabled=True,
    log_to_stdout=True,
    capture_python_logger=True,
    debug_mode=False,
    env="development"  # Add environment info
)
```

### Trace Context
The SDK automatically captures trace context for distributed tracing when available.

## Troubleshooting

1. **Logs not appearing**: Ensure the Lumberjack server is running (`lumberjack serve`)
2. **Connection errors**: Check that port 4317 is not in use
3. **Import errors**: Ensure you installed with the correct extras (e.g., `pip install 'lumberjack-sdk[local-server,flask]'`)

## What You Should Do Now

1. **Check for existing Lumberjack usage** first - if found, ONLY ensure `local_server_enabled=True`
2. **If no existing Lumberjack**, detect the framework by searching the codebase
3. **Add the dependency** with the correct extras:
   - Flask: `lumberjack-sdk[local-server,flask]`
   - FastAPI: `lumberjack-sdk[local-server,fastapi]`
   - Django: `lumberjack-sdk[local-server,django]`
   - Standalone: `lumberjack-sdk[local-server]`
4. **Add the initialization code** to the main application file with:
   - `api_key=""` (REQUIRED - empty string)
   - `local_server_enabled=True` (REQUIRED)
   - A descriptive `project_name` based on the project
   - `log_to_stdout=True`, `capture_python_logger=True`, `debug_mode=False`
5. **For web frameworks**: Also add the instrumentation call (LumberjackFlask.instrument(app), etc.)
6. **RESPECT existing settings** - do not modify existing configuration except for `local_server_enabled=True`

## Expected Changes

You should make 2-4 file changes:
1. Add the SDK to the dependency file (requirements.txt, pyproject.toml, or setup.py)
2. Add initialization code to the main application file
3. For web frameworks: Add instrumentation call
4. For Django only: Also update settings.py and apps.py

## Verification

After making the changes, the user will:
1. Install dependencies: `pip install -r requirements.txt` (or equivalent)
2. Start the Lumberjack server: `lumberjack serve`
3. Run the application
4. View logs at http://localhost:8080