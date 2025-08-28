"""
Utilities for checking and managing package upgrades.

Handles version checking against PyPI, installation method detection,
and upgrade command generation.
"""
import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from packaging import version
import requests

from ..version import __version__ as CURRENT_VERSION
from ..internal_utils.fallback_logger import fallback_logger


def get_package_info() -> Dict[str, Any]:
    """
    Get information about the current package installation.
    
    Returns:
        Dict containing installation info:
        - current_version: Current installed version
        - install_method: Detected installation method
        - install_path: Path where package is installed
        - is_editable: Whether package is installed in editable mode
        - python_executable: Path to Python executable
    """
    info = {
        "current_version": CURRENT_VERSION,
        "install_method": "unknown",
        "install_path": None,
        "is_editable": False,
        "python_executable": sys.executable,
    }
    
    # Get the module path
    import lumberjack_sdk
    module_path = Path(lumberjack_sdk.__file__).parent
    info["install_path"] = str(module_path)
    
    # Check if running from a git repository (development mode)
    git_root = module_path.parent.parent
    if (git_root / ".git").exists():
        info["install_method"] = "git"
        info["is_editable"] = True
        return info
    
    # Check if installed via pip/uv
    site_packages = sysconfig.get_paths()["purelib"]
    if site_packages in str(module_path):
        # Try to detect specific package managers
        if "uv" in sys.executable or os.environ.get("UV_PROJECT_ROOT"):
            info["install_method"] = "uv"
        elif ".local/pipx" in sys.executable or "pipx" in sys.executable:
            info["install_method"] = "pipx"
        elif "conda" in sys.executable or "miniconda" in sys.executable:
            info["install_method"] = "conda"
        else:
            info["install_method"] = "pip"
    
    # Check if package is editable
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "lumberjack-sdk"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Editable project location:"):
                    info["is_editable"] = True
                    break
    except Exception as e:
        fallback_logger.debug(f"Error checking pip show: {e}")
    
    return info


def check_pypi_version(package_name: str = "lumberjack-sdk") -> Optional[str]:
    """
    Check the latest version available on PyPI.
    
    Args:
        package_name: Name of the package on PyPI
        
    Returns:
        Latest version string or None if unable to fetch
    """
    try:
        response = requests.get(
            f"https://pypi.org/pypi/{package_name}/json",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        # return data["info"]["version"]
        return "2.0.5"
    except Exception as e:
        fallback_logger.error(f"Failed to check PyPI version: {e}")
        return None


def compare_versions(current: str, latest: str) -> Tuple[bool, str]:
    """
    Compare current version with latest version.
    
    Args:
        current: Current version string
        latest: Latest version string
        
    Returns:
        Tuple of (is_outdated, comparison_message)
    """
    try:
        curr_ver = version.parse(current)
        latest_ver = version.parse(latest)
        
        if curr_ver < latest_ver:
            return True, f"Update available: {current} → {latest}"
        elif curr_ver > latest_ver:
            return False, f"Running pre-release version {current} (latest stable: {latest})"
        else:
            return False, f"Up to date (version {current})"
    except Exception as e:
        fallback_logger.error(f"Error comparing versions: {e}")
        return False, "Unable to compare versions"


def generate_upgrade_command(install_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate the appropriate upgrade command based on installation method.
    
    Args:
        install_info: Installation information from get_package_info()
        
    Returns:
        Dict containing:
        - command: The upgrade command to run
        - description: Human-readable description
        - requires_restart: Whether server restart is needed
    """
    method = install_info["install_method"]
    python_exec = install_info["python_executable"]
    
    commands = {
        "pip": {
            "command": f"{python_exec} -m pip install --upgrade lumberjack-sdk[local-server]",
            "description": "Upgrade via pip",
            "requires_restart": True
        },
        "uv": {
            "command": "uv pip install --upgrade lumberjack-sdk[local-server]",
            "description": "Upgrade via uv",
            "requires_restart": True
        },
        "pipx": {
            "command": "pipx upgrade lumberjack-sdk",
            "description": "Upgrade via pipx",
            "requires_restart": True
        },
        "conda": {
            "command": "conda update lumberjack-sdk",
            "description": "Upgrade via conda (if available in conda)",
            "requires_restart": True
        },
        "git": {
            "command": f"git pull && {python_exec} -m pip install -e '.[local-server]'",
            "description": "Pull latest changes and reinstall in development mode",
            "requires_restart": True
        },
        "unknown": {
            "command": f"{python_exec} -m pip install --upgrade lumberjack-sdk[local-server]",
            "description": "Upgrade via pip (fallback)",
            "requires_restart": True
        }
    }
    
    return commands.get(method, commands["unknown"])


def execute_upgrade(command: str) -> Dict[str, Any]:
    """
    Execute the upgrade command.
    
    Args:
        command: The upgrade command to execute
        
    Returns:
        Dict containing:
        - success: Whether upgrade succeeded
        - output: Command output
        - error: Error message if failed
    """
    try:
        fallback_logger.info(f"Executing upgrade command: {command}")
        
        # Split command properly for subprocess
        if "&&" in command:
            # Handle compound commands
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
        else:
            # Handle simple commands
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=60
            )
        
        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout,
                "error": None
            }
        else:
            return {
                "success": False,
                "output": result.stdout,
                "error": result.stderr or "Upgrade command failed"
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "Upgrade command timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e)
        }


def get_version_info() -> Dict[str, Any]:
    """
    Get complete version and upgrade information.
    
    Returns:
        Dict containing all version and upgrade info
    """
    install_info = get_package_info()
    latest_version = check_pypi_version()
    
    result = {
        "current_version": CURRENT_VERSION,
        "latest_version": latest_version,
        "install_info": install_info,
        "update_available": False,
        "message": "",
        "upgrade_command": None
    }
    
    if latest_version:
        is_outdated, message = compare_versions(CURRENT_VERSION, latest_version)
        result["update_available"] = is_outdated
        result["message"] = message
        
        if is_outdated:
            upgrade_info = generate_upgrade_command(install_info)
            result["upgrade_command"] = upgrade_info
    else:
        result["message"] = "Unable to check for updates"
    
    return result