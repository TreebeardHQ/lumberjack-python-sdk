#!/usr/bin/env python3
"""
Test file to demonstrate improved IDE support with type stubs and enhanced docstrings.

Open this file in your IDE to test:
1. Hover over Lumberjack.init() to see detailed parameter descriptions
2. Use autocomplete to see all available parameters
3. Type checking should work correctly
4. Import statements should have proper type hints
"""

from lumberjack_sdk import Lumberjack, Log, LumberjackFastAPI
from lumberjack_sdk.core import Lumberjack as LumberjackCore


def test_ide_support() -> None:
    """Test IDE support features."""
    print("Testing IDE support for Lumberjack.init()...")
    
    # Hover over this call to see detailed parameter descriptions
    # Your IDE should show the comprehensive docstring with all parameter info
    Lumberjack.init(
        project_name="test-project",  # IDE should show: "Name of your project/application..."
        api_key="test-key",          # IDE should show: "Your Lumberjack API key..."
        debug_mode=True,             # IDE should show: "Enable verbose SDK debug logging..."
        local_server_enabled=False,  # IDE should show: "Enable local development server mode..."
        batch_size=100,              # IDE should show: "Maximum number of items in a batch..."
        env="development",           # IDE should show: "Environment name..."
        log_to_stdout=True,          # IDE should show: "Whether to also log to console..."
    )
    
    # Test direct instantiation (less common but should also work)
    print("Testing IDE support for Lumberjack() constructor...")
    # This should also show parameter descriptions when hovering
    instance = Lumberjack(
        project_name="direct-test",
        debug_mode=False
    )
    
    # Test autocomplete - type "Lumberjack." and see all available methods
    singleton_instance = Lumberjack.get_instance()
    
    # Test Log class autocomplete
    Log.info("Test message", key="value")
    
    print("✅ IDE support test completed!")
    print("Test both methods:")
    print("1. Hover over 'Lumberjack.init()' call above")
    print("2. Hover over 'Lumberjack()' constructor call above") 
    print("3. Type 'Lumberjack.' to see autocomplete")
    print("4. Both should show detailed parameter descriptions!")


if __name__ == "__main__":
    test_ide_support()