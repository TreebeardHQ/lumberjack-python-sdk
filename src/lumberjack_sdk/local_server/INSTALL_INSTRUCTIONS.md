# Lumberjack SDK Installation Instructions

## Your Task
You need to instrument this Python application with the Lumberjack SDK for local log collection. Follow these instructions carefully to make the necessary code changes.

## Overview
The Lumberjack SDK sends logs to a local GRPC collector on port 4317 for development purposes. You will be configuring it with the **LUMBERJACK_LOCAL_SERVER_ENABLED** environment variable which means:
- No API key is needed (automatically handled)
- Logs are sent to localhost:4317
- The user will view logs at http://localhost:8080

## Step 1: Check for Existing Lumberjack Installation

**IMPORTANT**: Before making changes, search the codebase for existing Lumberjack usage:

1. Search for `from lumberjack_sdk` or `import lumberjack_sdk`
2. Search for `Lumberjack.init(` or `LumberjackFlask` or `LumberjackFastAPI` or `LumberjackDjango`
3. Search for `LUMBERJACK_` in settings files

**If Lumberjack is already installed:**
- **DO NOT** change existing configuration parameters
- **ONLY** ensure the `LUMBERJACK_LOCAL_SERVER_ENABLED=true` environment variable is set
- **DO NOT** modify `project_name` or other existing settings
- Skip to Step 4 (Environment Setup)

**If Lumberjack is NOT installed, continue with Step 2.**

## Step 1.5: Environment Setup

Before configuring the SDK, you need to set the local server environment variable. Claude will:

1. **Check for existing environment configuration** (like .env files, docker-compose.yml, etc.)
2. **If found**: Add `LUMBERJACK_LOCAL_SERVER_ENABLED=true` to the existing configuration
3. **If not found**: Instruct you to add the environment variable to your development environment

**Environment variable to set:**
```bash
LUMBERJACK_LOCAL_SERVER_ENABLED=true
```

**Common ways to set this:**
- Add to `.env` file in your project root
- Export in your shell: `export LUMBERJACK_LOCAL_SERVER_ENABLED=true`
- Add to your IDE's run configuration
- Add to docker-compose.yml environment section

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

# Initialize Lumberjack - only project_name is required
# All other settings are automatically configured via environment variables
Lumberjack.init(
    project_name="my-flask-app"  # Replace with your project name
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

# Initialize Lumberjack - only project_name is required
# All other settings are automatically configured via environment variables
Lumberjack.init(
    project_name="my-fastapi-app"  # Replace with your project name
)

# Instrument FastAPI app
LumberjackFastAPI.instrument(app)
```

### For Django Applications

Add the following to your Django settings file (usually `settings.py`):

```python
import os
from lumberjack_sdk.lumberjack_django import LumberjackDjango

# Add Lumberjack configuration settings
LUMBERJACK_API_KEY = os.getenv("LUMBERJACK_API_KEY", "")  # Empty for local mode
LUMBERJACK_PROJECT_NAME = "my-django-app"  # Replace with your project name

# Initialize Lumberjack - automatically reads the settings above
LumberjackDjango.init()
```

**Alternative for production deployments:** You can also initialize in your `wsgi.py` or `asgi.py` file:

```python
# wsgi.py
import os
from django.core.wsgi import get_wsgi_application
from lumberjack_sdk.lumberjack_django import LumberjackDjango

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Initialize Lumberjack before creating WSGI application
LumberjackDjango.init()

application = get_wsgi_application()
```

### For Standalone Python Applications

At the top of your main Python file:

```python
import logging
from lumberjack_sdk import Lumberjack

# Initialize Lumberjack - only project_name is required
# All other settings are automatically configured via environment variables
Lumberjack.init(
    project_name="my-python-app"  # Replace with your project name
)

# Now all Python logging will be captured
logger = logging.getLogger(__name__)
logger.info("Application started with Lumberjack logging")
```

## Step 4: Verify Installation

After adding the initialization code:

1. Start the Lumberjack local server:
   ```bash
   lumberjack serve
   ```

2. Run your application

3. Check that logs appear in the web UI at http://localhost:8080

## Important Configuration Notes

- **LUMBERJACK_LOCAL_SERVER_ENABLED=true**: Environment variable that enables local server mode
- **project_name**: Use a descriptive name for your project/service (only required parameter)
- All other settings (API key, logging, etc.) are automatically configured when using local server mode

## Additional Features

### Custom Attributes
You can add environment variables or pass additional parameters to `Lumberjack.init()`:
```python
Lumberjack.init(
    project_name="my-app"
    # All other settings automatically configured via LUMBERJACK_LOCAL_SERVER_ENABLED
)
```

### Trace Context
The SDK automatically captures trace context for distributed tracing when available.

## Troubleshooting

1. **Logs not appearing**: Ensure the Lumberjack server is running (`lumberjack serve`)
2. **Connection errors**: Check that port 4317 is not in use and `LUMBERJACK_LOCAL_SERVER_ENABLED=true` is set
3. **Import errors**: Ensure you installed with the correct extras (e.g., `pip install 'lumberjack-sdk[local-server,flask]'`)

## What You Should Do Now

1. **Check for existing Lumberjack usage** first - if found, ONLY ensure `LUMBERJACK_LOCAL_SERVER_ENABLED=true` environment variable is set
2. **If no existing Lumberjack**, detect the framework by searching the codebase
3. **Add the dependency** with the correct extras:
   - Flask: `lumberjack-sdk[local-server,flask]`
   - FastAPI: `lumberjack-sdk[local-server,fastapi]`
   - Django: `lumberjack-sdk[local-server,django]`
   - Standalone: `lumberjack-sdk[local-server]`
4. **Add the initialization code** to the main application file with:
   - Only `project_name` parameter (REQUIRED)
   - Set `LUMBERJACK_LOCAL_SERVER_ENABLED=true` environment variable
5. **For web frameworks**: Also add the instrumentation call (LumberjackFlask.instrument(app), etc.)
6. **RESPECT existing settings** - do not modify existing configuration except for adding the environment variable

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