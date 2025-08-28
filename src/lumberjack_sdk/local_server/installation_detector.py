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


def find_uv_installation_path() -> Optional[str]:
    """Find the UV installation path for lumberjack-sdk."""
    try:
        # First try to find where uv installed lumberjack-sdk
        result = subprocess.run(
            ["uv", "pip", "show", "lumberjack-sdk"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Parse the output to find the installation location
            for line in result.stdout.split('\n'):
                if line.startswith('Location:'):
                    location = line.split(':', 1)[1].strip()
                    # Look for the script in the bin directory
                    bin_dir = Path(location).parent / "bin"
                    script_path = bin_dir / "lumberjack-mcp"
                    if script_path.exists():
                        return str(script_path)
        
        # Try to find UV tool installations
        result = subprocess.run(
            ["uv", "tool", "dir"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            tool_dir = result.stdout.strip()
            # Look for lumberjack installation in tool directory
            if tool_dir:  # Make sure tool_dir is not empty
                possible_paths = [
                    Path(tool_dir) / "lumberjack-sdk" / "bin" / "lumberjack-mcp",
                    Path(tool_dir) / "lumberjack_sdk" / "bin" / "lumberjack-mcp",
                ]
                
                for path in possible_paths:
                    if path.exists():
                        return str(path)
        
        return None
        
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def test_mcp_command(method: InstallationMethod) -> bool:
    """Test if an MCP command actually works."""
    try:
        cmd = [method.command] + method.args + ["--help"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=5  # Shorter timeout to avoid hanging
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def test_mcp_command_local_dev(method: InstallationMethod) -> bool:
    """Test if an MCP command works for local development (allows unpublished packages)."""
    try:
        # For uvx method, try to run from local source
        if method.name == "uvx" and "lumberjack-sdk" in str(method.args):
            # Test if we can run from current directory
            cmd = ["uvx", "--from", ".", "lumberjack-mcp", "--help"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
                cwd=Path(__file__).parent.parent.parent.parent  # Go to project root
            )
            return result.returncode == 0
        else:
            return test_mcp_command(method)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return test_mcp_command(method)  # Fallback to original test


def detect_installation_method() -> Tuple[Optional[InstallationMethod], str]:
    """
    Detect how lumberjack-sdk was installed and return the best MCP configuration.
    
    Returns:
        Tuple of (InstallationMethod or None, status_message)
    """
    
    # Method 1: Try uvx (most robust for any UV installation)
    if check_command_available("uvx"):
        # First try published package
        method = InstallationMethod(
            name="uvx",
            command="uvx", 
            args=["--from", "lumberjack-sdk[local-server]", "lumberjack-mcp"],
            description="Using uvx to run lumberjack-mcp (recommended)"
        )
        
        if test_mcp_command(method):
            return method, f"✅ Detected uvx installation method"
        
        # If published package fails, try local development version
        local_method = InstallationMethod(
            name="uvx_local",
            command="uvx", 
            args=["--from", ".", "lumberjack-mcp"],
            description="Using uvx to run lumberjack-mcp from local source (development)"
        )
        
        if test_mcp_command_local_dev(local_method):
            return local_method, f"✅ Detected uvx with local development setup"
        else:
            fallback_logger.warning("uvx is available but lumberjack-mcp test failed for both published and local versions")
    
    # Method 2: Check global PATH (standard pip install)
    if check_command_available("lumberjack-mcp"):
        method = InstallationMethod(
            name="global",
            command="lumberjack-mcp",
            description="Using lumberjack-mcp from PATH (standard pip install)"
        )
        
        if test_mcp_command(method):
            return method, f"✅ Detected lumberjack-mcp in global PATH"
    
    # Method 3: Find UV installation path
    uv_path = find_uv_installation_path()
    if uv_path:
        method = InstallationMethod(
            name="uv_direct",
            command=uv_path,
            description=f"Using direct path to UV installation: {uv_path}"
        )
        
        if test_mcp_command(method):
            return method, f"✅ Detected UV installation at {uv_path}"
        else:
            fallback_logger.warning(f"Found UV path {uv_path} but command test failed")
    
    # Method 4: Check common UV locations
    possible_uv_paths = [
        Path.home() / ".local" / "bin" / "lumberjack-mcp",
        Path.home() / ".cargo" / "bin" / "lumberjack-mcp", 
        Path("/usr/local/bin/lumberjack-mcp"),
        Path("/opt/homebrew/bin/lumberjack-mcp"),
    ]
    
    for path in possible_uv_paths:
        if path.exists():
            method = InstallationMethod(
                name="manual_path",
                command=str(path),
                description=f"Using manually found path: {path}"
            )
            
            if test_mcp_command(method):
                return method, f"✅ Detected lumberjack-mcp at {path}"
    
    # No working method found
    return None, "❌ Could not detect a working lumberjack-mcp installation"


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
                   f"1. Install with uvx: uvx --from 'lumberjack-sdk[local-server]' lumberjack-mcp\n" \
                   f"2. Use regular pip: pip install 'lumberjack-sdk[local-server]'\n" \
                   f"3. Add UV bin directory to your PATH\n" \
                   f"4. Use uv tool install: uv tool install lumberjack-sdk[local-server]"
        
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
    return method is not None and test_mcp_command(method)


if __name__ == "__main__":
    # CLI for testing the detection
    method, status = detect_installation_method()
    print(status)
    
    if method:
        print(f"Method: {method.name}")
        print(f"Command: {method}")
        print(f"MCP Config: {method.to_mcp_config()}")
        
        # Test the command
        print(f"Testing command: ", end="", flush=True)
        if test_mcp_command(method):
            print("✅ PASSED")
        else:
            print("❌ FAILED")
    else:
        print("No working installation method found.")
        sys.exit(1)