"""
Tests for the core functionality.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from lumberjack_sdk.core import Lumberjack
from lumberjack_sdk.internal_utils.fallback_logger import fallback_logger, sdk_logger


@pytest.fixture(autouse=True)
def reset_lumberjack():
    """Reset Lumberjack singleton between tests."""
    yield
    Lumberjack.reset()


def test_init_valid_api_key():
    api_key = "test-api-key"
    Lumberjack.init(api_key=api_key, endpoint="https://test.endpoint")
    client = Lumberjack()
    assert client.api_key == api_key
    assert client._endpoint == "https://test.endpoint"


def test_singleton_behavior():
    api_key = "test-api-key"
    Lumberjack.init(api_key=api_key,
                    endpoint="https://test.endpoint")

    instance1 = Lumberjack()
    instance2 = Lumberjack()

    assert instance1 is instance2
    assert instance1.api_key == instance2.api_key == api_key


def test_init_empty_api_key():
    """Test that empty API key triggers no-op mode."""
    # Test with empty string
    Lumberjack.reset()
    Lumberjack.init(api_key="")
    instance = Lumberjack()
    assert instance.is_noop is True
    assert instance._using_fallback is False


def test_uninitialized_client():
    Lumberjack.init()
    instance = Lumberjack()
    assert instance._api_key is None


def test_fallback_logger_level():
    """Test that fallback logger is configured with INFO level."""
    assert fallback_logger.level == logging.INFO


def test_switching_between_modes(reset_lumberjack):
    """Test switching between no-op and API modes."""
    # Start with no-op mode (no API key, no local server, no custom exporters)
    Lumberjack.init()
    instance = Lumberjack()
    assert instance.is_noop is True
    assert instance._using_fallback is False

    # Reset and switch to API mode
    Lumberjack.reset()
    Lumberjack.init(api_key="test-key", endpoint="http://test.com")
    instance = Lumberjack()
    assert instance.is_noop is False
    assert instance._using_fallback is False

    # Verify API mode is properly configured
    assert instance._api_key == "test-key"
    assert instance._endpoint == "http://test.com"


def test_project_name_initialization(reset_lumberjack):
    """Test that project_name is properly set and sent to API."""
    project_name = "test-project"

    # Mock the LumberjackLogExporter class
    with patch('lumberjack_sdk.core.LumberjackLogExporter') as MockExporter:
        # Create a mock exporter instance
        mock_exporter = MagicMock()
        MockExporter.return_value = mock_exporter

        # Initialize with project_name
        Lumberjack.init(project_name=project_name,
                        api_key="test-key", endpoint="http://test.com")
        instance = Lumberjack()

        # Verify project_name is set
        assert instance._project_name == project_name

        # Verify exporter was initialized with correct parameters
        MockExporter.assert_called_once()
        call_args = MockExporter.call_args[1]
        assert call_args['api_key'] == "test-key"
        assert call_args['project_name'] == project_name


def test_project_name_not_overwritten_on_reinitialization(reset_lumberjack):
    """Test that project_name can be updated on subsequent init calls."""
    # First initialization
    Lumberjack.init(project_name="first-project",
                    api_key="test-key", endpoint="http://test.com")
    instance = Lumberjack()
    assert instance._project_name == "first-project"

    # Second initialization with different project_name (should update)
    Lumberjack.init(project_name="second-project")
    assert instance._project_name == "second-project"


def test_project_name_none_when_not_provided(reset_lumberjack):
    """Test that project_name is None when not provided during initialization."""
    # Mock the LumberjackLogExporter class
    with patch('lumberjack_sdk.core.LumberjackLogExporter') as MockExporter:
        # Create a mock exporter instance
        mock_exporter = MagicMock()
        MockExporter.return_value = mock_exporter

        Lumberjack.init(api_key="test-key", endpoint="http://test.com")
        instance = Lumberjack()

        # Should be None when not provided
        assert instance._project_name is None

        # Verify exporter was initialized with correct parameters
        MockExporter.assert_called_once()
        call_args = MockExporter.call_args[1]
        assert call_args['api_key'] == "test-key"
        assert call_args['project_name'] is None


def test_project_name_reset(reset_lumberjack):
    """Test that project_name is properly reset."""
    # Initialize with project_name
    Lumberjack.init(project_name="test-project",
                    api_key="test-key", endpoint="http://test.com")
    instance = Lumberjack()
    assert instance._project_name == "test-project"

    # Reset should clear project_name
    Lumberjack.reset()

    # New instance should have None project_name
    Lumberjack.init(api_key="test-key", endpoint="http://test.com")
    instance = Lumberjack()
    assert instance._project_name is None


def test_project_name_reset_on_reinit(reset_lumberjack):
    """Test the original bug scenario where project_name gets sent as None to API."""
    # This test reproduces the original issue described by the user

    # Initialize Lumberjack with a project name
    Lumberjack.init(project_name="my-project",
                    api_key="test-key", endpoint="http://test.com")
    instance = Lumberjack()

    # Verify initial project_name is correct
    assert instance._project_name == "my-project"

    # Simulate another initialization call (which could happen in some codebases)
    # Before the fix, this would cause project_name to be ignored due to early return
    Lumberjack.init(api_key="test-key", endpoint="http://test.com")

    # After the fix,
    # project_name should still be "my-project"
    # since no new project_name was provided
    assert instance._project_name == "my-project"

    # Now test with a different project name - should update
    Lumberjack.init(project_name="updated-project")
    assert instance._project_name == "updated-project"