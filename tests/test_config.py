"""Tests for configuration handling, especially environment variables."""

import os
import unittest
from unittest.mock import patch

from lumberjack_sdk.config import LumberjackConfig
from lumberjack_sdk.core import Lumberjack


class TestConfigEnvironmentVariables(unittest.TestCase):
    """Test environment variable handling in configuration."""

    def setUp(self):
        """Reset environment before each test."""
        # Save original env vars
        self.original_env = os.environ.copy()
        
        # Clear all LUMBERJACK_* env vars
        for key in list(os.environ.keys()):
            if key.startswith('LUMBERJACK_'):
                del os.environ[key]
    
    def tearDown(self):
        """Restore original environment."""
        # Clear all env vars
        os.environ.clear()
        # Restore original
        os.environ.update(self.original_env)
        
        # Reset Lumberjack singleton
        if Lumberjack._instance:
            try:
                Lumberjack._instance.shutdown()
            except:
                pass
        Lumberjack._instance = None
        Lumberjack._initialized = False

    def test_local_server_enabled_env_var_in_config(self):
        """Test that LUMBERJACK_LOCAL_SERVER_ENABLED env var is respected in config."""
        # Set environment variable
        os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = 'true'
        
        # Create config with no arguments
        config = LumberjackConfig()
        
        # Verify local_server_enabled was set from environment
        self.assertTrue(config.local_server_enabled)
        self.assertTrue(config.should_use_local_server())
    
    def test_local_server_disabled_env_var_in_config(self):
        """Test that LUMBERJACK_LOCAL_SERVER_ENABLED=false is respected."""
        # Set environment variable
        os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = 'false'
        
        # Create config with no arguments
        config = LumberjackConfig()
        
        # Verify local_server_enabled is False
        self.assertFalse(config.local_server_enabled)
        self.assertFalse(config.should_use_local_server())
    
    def test_local_server_enabled_various_true_values(self):
        """Test that various 'true' values are recognized."""
        true_values = ['true', 'True', 'TRUE', '1', 'yes', 'YES', 'on', 'ON']
        
        for value in true_values:
            os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = value
            config = LumberjackConfig()
            self.assertTrue(config.local_server_enabled, 
                          f"Failed to recognize '{value}' as true")
            # Clean up for next iteration
            del os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED']
    
    def test_local_server_enabled_various_false_values(self):
        """Test that various 'false' values are recognized."""
        false_values = ['false', 'False', 'FALSE', '0', 'no', 'NO', 'off', 'OFF']
        
        for value in false_values:
            os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = value
            config = LumberjackConfig()
            self.assertFalse(config.local_server_enabled,
                           f"Failed to recognize '{value}' as false")
            # Clean up for next iteration
            del os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED']
    
    def test_local_server_enabled_env_var_with_lumberjack_init(self):
        """Test that Lumberjack.init() respects LUMBERJACK_LOCAL_SERVER_ENABLED."""
        # Set environment variable
        os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = 'true'
        os.environ['LUMBERJACK_LOCAL_SERVER_SERVICE_NAME'] = 'test-service'
        
        # Initialize Lumberjack with no local_server_enabled argument
        Lumberjack.init(project_name="test-project")
        
        # Get the instance and check its config
        instance = Lumberjack.get_instance()
        self.assertIsNotNone(instance)
        self.assertIsNotNone(instance._config)
        self.assertTrue(instance._config.local_server_enabled)
        self.assertTrue(instance._config.should_use_local_server())
        self.assertEqual(instance._config.local_server_service_name, 'test-service')
    
    def test_local_server_enabled_explicit_overrides_env(self):
        """Test that explicit parameter overrides environment variable."""
        # Set environment variable to true
        os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = 'true'
        
        # Initialize with explicit False
        Lumberjack.init(
            project_name="test-project",
            local_server_enabled=False
        )
        
        # Get the instance and check its config
        instance = Lumberjack.get_instance()
        self.assertIsNotNone(instance)
        self.assertFalse(instance._config.local_server_enabled)
        self.assertFalse(instance._config.should_use_local_server())
    
    def test_local_server_initialization_in_fallback_mode(self):
        """Test that local server is initialized even in fallback mode."""
        # Set environment variable
        os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = 'true'
        
        # Initialize without API key (fallback mode)
        Lumberjack.init(project_name="test-project")
        
        instance = Lumberjack.get_instance()
        self.assertIsNotNone(instance)
        
        # Should be in fallback mode (no API key)
        self.assertTrue(instance._config.is_fallback_mode())
        
        # But local server should still be enabled
        self.assertTrue(instance._config.should_use_local_server())
        
        # Check that local server processor was created
        # The processor is added during initialization
        self.assertIsNotNone(instance._logger_provider)
    
    def test_multiple_env_vars(self):
        """Test that multiple environment variables are all respected."""
        # Set multiple environment variables
        os.environ['LUMBERJACK_LOCAL_SERVER_ENABLED'] = 'true'
        os.environ['LUMBERJACK_LOCAL_SERVER_SERVICE_NAME'] = 'my-service'
        os.environ['LUMBERJACK_DEBUG_MODE'] = 'true'
        os.environ['LUMBERJACK_LOG_TO_STDOUT'] = 'false'
        os.environ['LUMBERJACK_PROJECT_NAME'] = 'env-project'
        
        # Create config
        config = LumberjackConfig()
        
        # Verify all were applied
        self.assertTrue(config.local_server_enabled)
        self.assertEqual(config.local_server_service_name, 'my-service')
        self.assertTrue(config.debug_mode)
        self.assertFalse(config.log_to_stdout)
        self.assertEqual(config.project_name, 'env-project')


if __name__ == '__main__':
    unittest.main()