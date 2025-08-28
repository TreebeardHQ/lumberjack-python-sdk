"""
Installation detection utilities for Lumberjack SDK.

Detects how lumberjack-sdk was installed and provides the appropriate
MCP command configuration for Claude Desktop and Cursor.
"""
import os
import subprocess
import sys
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

try:
    from ..internal_utils.fallback_logger import fallback_logger
except ImportError:
    # Fallback for direct execution - create a simple logger
    import logging
    fallback_logger = logging.getLogger(__name__)


class InstallationMethod:
    """Represents an installation method and its MCP configuration."""
    
    def __init__(self, name: str, command: str, args: Optional[list] = None, description: str = ""):
        self.name = name
        self.command = command
        self.args = args or []
        self.description = description
    
    def to_mcp_config(self) -> Dict[str, Any]:
        """Convert to MCP configuration format."""
        config = {"command": self.command}
        if self.args:
            config["args"] = self.args
        return config
    
    def __str__(self) -> str:
        if self.args:
            return f"{self.command} {' '.join(self.args)}"
        return self.command


def check_command_available(command: str) -> bool:
    """Check if a command is available in PATH."""
    try:
        subprocess.run([command, "--version"], 
                      capture_output=True, 
                      check=True, 
                      timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        try:
            # Try 'which' as fallback for commands without --version
            subprocess.run(["which", command], 
                          capture_output=True, 
                          check=True, 
                          timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False


def install_with_uv_tool() -> Tuple[bool, str]:
    """
    Install lumberjack-sdk as a UV tool.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not check_command_available("uv"):
        return False, "❌ UV not available"
    
    try:
        print("📦 Installing lumberjack-sdk as UV tool...")
        result = subprocess.run(
            ["uv", "tool", "install", "lumberjack-sdk"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Verify installation worked
            if check_command_available("lumberjack-mcp"):
                return True, "✅ Successfully installed lumberjack-sdk as UV tool"
            else:
                return False, "❌ Installation completed but lumberjack-mcp not found in PATH"
        else:
            # Check if already installed
            if "already installed" in result.stderr.lower():
                if check_command_available("lumberjack-mcp"):
                    return True, "✅ lumberjack-sdk already installed as UV tool"
                else:
                    return False, "❌ lumberjack-sdk installed but lumberjack-mcp not in PATH"
            else:
                return False, f"❌ UV tool install failed: {result.stderr}"
                
    except subprocess.TimeoutExpired:
        return False, "❌ UV tool install timed out"
    except Exception as e:
        return False, f"❌ UV tool install error: {str(e)}"


def detect_installation_method() -> Tuple[Optional[InstallationMethod], str]:
    """
    Detect how lumberjack-sdk is installed and return the best MCP configuration.
    
    Returns:
        Tuple of (InstallationMethod or None, status_message)
    """
    
    # Method 1: Check if lumberjack-mcp is already available in PATH
    if check_command_available("lumberjack-mcp"):
        method = InstallationMethod(
            name="global",
            command="lumberjack-mcp",
            description="Using lumberjack-mcp from PATH"
        )
        return method, f"✅ Found lumberjack-mcp in PATH"
    
    # Method 2: Try installing with UV tool if UV is available
    if check_command_available("uv"):
        success, message = install_with_uv_tool()
        if success:
            method = InstallationMethod(
                name="uv_tool",
                command="lumberjack-mcp",
                description="Using lumberjack-mcp installed via UV tool"
            )
            return method, message
        else:
            fallback_logger.warning(f"UV tool install failed: {message}")
    
    # No working method found
    return None, "❌ Could not detect or install lumberjack-mcp"


def get_mcp_config_for_editor(editor: str = "cursor") -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Get MCP configuration for a specific editor.
    
    Args:
        editor: Editor name ("cursor" or "claude")
        
    Returns:
        Tuple of (mcp_config_dict or None, status_message)
    """
    method, status = detect_installation_method()
    
    if method is None:
        error_msg = f"{status}\n\n" \
                   f"💡 Try one of these solutions:\n" \
                   f"1. Use regular pip: pip install 'lumberjack-sdk[local-server]'\n" \
                   f"2. Use uv tool install: uv tool install lumberjack-sdk\n" \
                   f"3. Make sure lumberjack-mcp is in your PATH"
        
        return None, error_msg
    
    # Create the MCP server configuration
    config = {
        "mcpServers": {
            "lumberjack": method.to_mcp_config()
        }
    }
    
    success_msg = f"{status}\n" \
                 f"📋 Using method: {method.description}\n" \
                 f"🔧 Command: {method}"
    
    return config, success_msg


def validate_mcp_setup() -> bool:
    """
    Validate that MCP setup will work.
    
    Returns:
        True if setup is valid, False otherwise
    """
    method, _ = detect_installation_method()
    return method is not None


if __name__ == "__main__":
    # CLI for testing the detection
    method, status = detect_installation_method()
    print(status)
    
    if method:
        print(f"Method: {method.name}")
        print(f"Command: {method}")
        print(f"MCP Config: {method.to_mcp_config()}")
        print("✅ Detection successful")
    else:
        print("No working installation method found.")
        sys.exit(1)