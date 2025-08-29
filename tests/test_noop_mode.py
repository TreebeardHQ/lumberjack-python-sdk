"""
Tests for the no-op mode functionality.

The SDK should be a no-op in production if:
1. local_server_enabled is False (or None)
2. No API key is configured
3. No custom exporters are configured
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

from lumberjack_sdk.core import Lumberjack
from lumberjack_sdk.exception_handlers import ExceptionHandlers


@pytest.fixture(autouse=True)
def reset_lumberjack():
    """Reset Lumberjack singleton between tests."""
    yield
    Lumberjack.reset()


def test_noop_mode_with_all_conditions_met():
    """Test that SDK operates in no-op mode when all three conditions are met."""
    # Initialize with no API key, no local server, no custom exporters
    Lumberjack.init(
        project_name="test-project",
        local_server_enabled=False,  # Condition 1: explicitly disabled
        api_key=None,  # Condition 2: no API key
        # Condition 3: no custom exporters (not provided)
    )
    
    instance = Lumberjack()
    
    # Verify SDK is in no-op mode
    assert instance.is_noop is True
    
    # Verify no components were initialized
    assert instance._flush_timer is None
    assert instance._object_registration is None
    assert instance._tracer_provider is None
    assert instance._logger_provider is None
    assert instance._meter_provider is None
    
    # Verify properties return None in no-op mode
    assert instance.tracer is None
    assert instance.logger is None
    assert instance.meter is None
    
    # Verify methods handle no-op gracefully
    instance.register_object({"id": "test"})  # Should not error
    assert instance.flush_objects() == 0  # Should return 0
    instance.shutdown()  # Should not error


def test_noop_mode_with_env_var_false():
    """Test no-op mode when local server is disabled via environment variable."""
    with patch.dict('os.environ', {'LUMBERJACK_LOCAL_SERVER_ENABLED': 'false'}):
        Lumberjack.init(
            project_name="test-project",
            # local_server_enabled will be False from env var
            # No API key
            # No custom exporters
        )
        
        instance = Lumberjack()
        assert instance.is_noop is True


def test_noop_mode_with_local_server_not_set():
    """Test no-op mode when local_server_enabled is not set (defaults to None)."""
    Lumberjack.init(
        project_name="test-project",
        # local_server_enabled not set (None)
        # No API key
        # No custom exporters
    )
    
    instance = Lumberjack()
    assert instance.is_noop is True


def test_not_noop_with_api_key():
    """Test that SDK is NOT in no-op mode when API key is provided."""
    Lumberjack.init(
        project_name="test-project",
        api_key="test-api-key",  # API key provided
        local_server_enabled=False,
    )
    
    instance = Lumberjack()
    assert instance.is_noop is False
    
    # Verify components were initialized
    assert instance._flush_timer is not None
    assert instance._object_registration is not None


def test_not_noop_with_local_server_enabled():
    """Test that SDK is NOT in no-op mode when local server is enabled."""
    Lumberjack.init(
        project_name="test-project",
        local_server_enabled=True,  # Local server enabled
        api_key=None,  # No API key
    )
    
    instance = Lumberjack()
    assert instance.is_noop is False


def test_not_noop_with_custom_log_exporter():
    """Test that SDK is NOT in no-op mode when custom log exporter is provided."""
    mock_exporter = MagicMock()
    
    Lumberjack.init(
        project_name="test-project",
        local_server_enabled=False,
        api_key=None,
        custom_log_exporter=mock_exporter,  # Custom exporter provided
    )
    
    instance = Lumberjack()
    assert instance.is_noop is False


def test_not_noop_with_custom_span_exporter():
    """Test that SDK is NOT in no-op mode when custom span exporter is provided."""
    mock_exporter = MagicMock()
    
    Lumberjack.init(
        project_name="test-project",
        local_server_enabled=False,
        api_key=None,
        custom_span_exporter=mock_exporter,  # Custom exporter provided
    )
    
    instance = Lumberjack()
    assert instance.is_noop is False


def test_not_noop_with_custom_metrics_exporter():
    """Test that SDK is NOT in no-op mode when custom metrics exporter is provided."""
    mock_exporter = MagicMock()
    
    Lumberjack.init(
        project_name="test-project",
        local_server_enabled=False,
        api_key=None,
        custom_metrics_exporter=mock_exporter,  # Custom exporter provided
    )
    
    instance = Lumberjack()
    assert instance.is_noop is False


def test_exception_handlers_not_registered_in_noop():
    """Test that exception handlers are not registered in no-op mode."""
    # Store original handler
    original_handler = sys.excepthook
    
    try:
        # Initialize in no-op mode
        Lumberjack.init(
            project_name="test-project",
            local_server_enabled=False,
            api_key=None,
        )
        
        # Verify exception handler was not changed
        assert sys.excepthook == original_handler
        
        # Verify ExceptionHandlers class shows not registered
        assert ExceptionHandlers._registered is False
        
    finally:
        # Restore original handler just in case
        sys.excepthook = original_handler


def test_noop_mode_with_empty_api_key():
    """Test no-op mode when API key is empty string."""
    Lumberjack.init(
        project_name="test-project",
        api_key="",  # Empty string API key
        local_server_enabled=False,
    )
    
    instance = Lumberjack()
    assert instance.is_noop is True


def test_noop_mode_with_whitespace_api_key():
    """Test no-op mode when API key is only whitespace."""
    Lumberjack.init(
        project_name="test-project",
        api_key="   ",  # Whitespace-only API key
        local_server_enabled=False,
    )
    
    instance = Lumberjack()
    assert instance.is_noop is True


def test_signal_handlers_not_installed_in_noop():
    """Test that signal handlers are not installed in no-op mode."""
    with patch('lumberjack_sdk.core._signal_handlers_installed', False):
        # Initialize in no-op mode
        Lumberjack.init(
            project_name="test-project",
            local_server_enabled=False,
            api_key=None,
            install_signal_handlers=True,  # Request signal handlers
        )
        
        # Import the flag after initialization
        from lumberjack_sdk.core import _signal_handlers_installed
        
        # Verify signal handlers were not installed even though requested
        assert _signal_handlers_installed is False


def test_stdout_override_not_enabled_in_noop():
    """Test that stdout override is not enabled in no-op mode."""
    with patch('lumberjack_sdk.stdout_override.StdoutOverride.enable') as mock_enable:
        # Initialize in no-op mode with capture_stdout=True
        Lumberjack.init(
            project_name="test-project",
            local_server_enabled=False,
            api_key=None,
            capture_stdout=True,  # Request stdout capture
        )
        
        # Verify enable was not called
        mock_enable.assert_not_called()


def test_python_logger_forwarding_not_enabled_in_noop():
    """Test that Python logger forwarding is not enabled in no-op mode."""
    with patch('lumberjack_sdk.logging_instrumentation.enable_python_logger_forwarding') as mock_enable:
        # Initialize in no-op mode with capture_python_logger=True
        Lumberjack.init(
            project_name="test-project",
            local_server_enabled=False,
            api_key=None,
            capture_python_logger=True,  # Request logger capture
        )
        
        # Verify enable was not called
        mock_enable.assert_not_called()