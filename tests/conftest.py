"""
Configure pytest to find the source package
"""
import os
import sys

import pytest

# Add the src directory to the Python path
src_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, src_path)
path_updated = True

@pytest.fixture(autouse=True)
def reset_context():
    """Reset context between tests."""
    # Context is now managed by OpenTelemetry
    yield


@pytest.fixture(autouse=True)
def clean_modules():
    """Temporarily remove gevent and eventlet from sys.modules if present."""
    # Clean modules for testing
    saved_modules = {}
    for name in ['gevent',
                 'eventlet',
                 'gevent.local',
                 'eventlet.core',
                 'eventlet.coros',
                 'eventlet.corolocal',
                 'eventlet.green.threading']:
        if name in sys.modules:
            saved_modules[name] = sys.modules[name]
            del sys.modules[name]
    yield
    # Restore the saved modules
    for name, module in saved_modules.items():
        sys.modules[name] = module
