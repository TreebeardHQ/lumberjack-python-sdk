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

Add `LUMBERJACK_LOCAL_SERVER_ENABLED=true` to your project's `.env` file to enable local development mode:

```bash
LUMBERJACK_LOCAL_SERVER_ENABLED=true
```

This will automatically configure the SDK to send logs to your local Lumberjack server instead of the production API.

## Step 2: Detect the Web Framework and Configuration Management
Search the codebase to determine which framework is being used:

1. **Flask**: Search for `from flask import Flask` or `Flask(__name__)` 
2. **FastAPI**: Search for `from fastapi import FastAPI` or `FastAPI()`
3. **Django**: Search for `django` in requirements.txt or settings.py files
4. **None**: If none of the above are found, treat it as a standalone Python application

## Step 2.5: Detect Pydantic BaseSettings Usage
Search the codebase to determine if the application uses pydantic BaseSettings for configuration:

1. Search for `from pydantic_settings import BaseSettings` or `from pydantic import BaseSettings`
2. Search for classes that inherit from `BaseSettings`
3. Look for files named `config.py`, `settings.py`, or similar configuration files
4. If found, note the settings class name and file location - you'll need to modify this class

## Step 3: Add the SDK to Dependencies

**Important:** The `local-server` extra is only for development. Add dependencies as follows:

### For Production Dependencies (without local-server):

**Flask applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk[flask]`
- If `pyproject.toml` exists, add to `dependencies`: `"lumberjack-sdk[flask]"`

**FastAPI applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk[fastapi]`
- If `pyproject.toml` exists, add to `dependencies`: `"lumberjack-sdk[fastapi]"`

**Django applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk[django]`
- If `pyproject.toml` exists, add to `dependencies`: `"lumberjack-sdk[django]"`

**Standalone Python applications:**
- If `requirements.txt` exists, add: `lumberjack-sdk`
- If `pyproject.toml` exists, add to `dependencies`: `"lumberjack-sdk"`

### For Development Dependencies (with local-server):

Add to development/optional dependencies:

**If using `requirements-dev.txt`:**
- Flask: `lumberjack-sdk[local-server,flask]`
- FastAPI: `lumberjack-sdk[local-server,fastapi]`
- Django: `lumberjack-sdk[local-server,django]`
- Standalone: `lumberjack-sdk[local-server]`

**If using `pyproject.toml` with optional dependencies:**
```toml
[project.optional-dependencies]
dev = [
    "lumberjack-sdk[local-server,flask]",  # or fastapi/django as appropriate
    # ... other dev dependencies
]
```

**If the project doesn't have separate dev dependencies:**
- Add to main requirements with comment: `lumberjack-sdk[local-server,flask]  # local-server only needed for development`

## Step 3.5: Configure Pydantic BaseSettings (if detected in Step 2.5)

If the application uses pydantic BaseSettings for configuration management, you MUST update the settings class to prevent validation errors and enable proper integration:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Your existing settings...
    
    # Add Lumberjack settings to prevent validation errors
    # The field names must match the env var names (lowercase with underscores)
    lumberjack_local_server_enabled: bool = False
    lumberjack_project_name: str = "my-app"  # Replace with your app name
    lumberjack_api_key: str = ""  # Empty for local mode
    lumberjack_env: str = "development"
    
    class Config:
        env_file = ".env"
        # Note: Even without explicit extra="forbid", pydantic-settings 
        # may enforce validation, so always add the fields above

# Create a settings instance (usually done in your main config file)
settings = Settings()
```

**Why this is necessary:** Pydantic BaseSettings validates environment variables against your Settings class fields. Without these fields defined, you'll get validation errors when the `LUMBERJACK_*` environment variables are present in your `.env` file.

**Integration with Lumberjack:** Once configured, you'll use the settings object in Lumberjack.init() instead of environment variables (shown in Step 4).

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

**If using Pydantic BaseSettings:** Use the settings object instead:
```python
from flask import Flask
from lumberjack_sdk import Lumberjack, LumberjackFlask
from .config import settings  # Import your settings instance

app = Flask(__name__)

# Initialize Lumberjack using pydantic settings
Lumberjack.init(
    project_name=settings.lumberjack_project_name,
    local_server_enabled=settings.lumberjack_local_server_enabled,
    api_key=settings.lumberjack_api_key,
    env=settings.lumberjack_env,
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

**If using Pydantic BaseSettings:** Use the settings object instead:
```python
from fastapi import FastAPI
from lumberjack_sdk import Lumberjack, LumberjackFastAPI
from .config import settings  # Import your settings instance

app = FastAPI()

# Initialize Lumberjack using pydantic settings
Lumberjack.init(
    project_name=settings.lumberjack_project_name,
    local_server_enabled=settings.lumberjack_local_server_enabled,
    api_key=settings.lumberjack_api_key,
    env=settings.lumberjack_env,
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

**If using Pydantic BaseSettings:** Use the settings object instead:
```python
import logging
from lumberjack_sdk import Lumberjack
from .config import settings  # Import your settings instance

# Initialize Lumberjack using pydantic settings
Lumberjack.init(
    project_name=settings.lumberjack_project_name,
    local_server_enabled=settings.lumberjack_local_server_enabled,
    api_key=settings.lumberjack_api_key,
    env=settings.lumberjack_env,
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

1. **Check for existing Lumberjack usage** first - if found, ONLY add `LUMBERJACK_LOCAL_SERVER_ENABLED=true` to your `.env` file
2. **If no existing Lumberjack**, detect the framework by searching the codebase
3. **Add the dependency** with the correct extras:
   - **Production deps**: `lumberjack-sdk[flask]` (or fastapi/django)
   - **Dev deps**: `lumberjack-sdk[local-server,flask]` (or fastapi/django)
   - Prefer adding `local-server` to dev dependencies when possible
4. **Add the initialization code** to the main application file with:
   - Only `project_name` parameter (REQUIRED)
   - Add `LUMBERJACK_LOCAL_SERVER_ENABLED=true` to your `.env` file
5. **For web frameworks**: Also add the instrumentation call (LumberjackFlask.instrument(app), etc.)
6. **For Pydantic BaseSettings**: ALWAYS update Settings class to include LUMBERJACK_* fields and use settings object in Lumberjack.init()
7. **RESPECT existing settings** - do not modify existing configuration except for adding `LUMBERJACK_LOCAL_SERVER_ENABLED=true` to `.env`

## Expected Changes

You should make 2-5 file changes:
1. Add the SDK to the dependency file (preferably dev dependencies for local-server)
2. Add initialization code to the main application file
3. For web frameworks: Add instrumentation call
4. For Django only: Also update settings.py and apps.py
5. For Pydantic BaseSettings: ALWAYS update Settings class to add LUMBERJACK_* fields and use in Lumberjack.init()

## Verification

After making the changes, the user will:
1. Install dependencies: `pip install -r requirements.txt` (or equivalent)
2. Start the Lumberjack server: `lumberjack serve`
3. Run the application
4. View logs at http://localhost:8080