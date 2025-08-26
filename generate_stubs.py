#!/usr/bin/env python3
"""
Generate type stub files for the lumberjack_sdk package.

This script regenerates .pyi stub files using mypy's stubgen tool.
Run this after making significant changes to the codebase to keep 
stub files up to date.

Usage:
    python generate_stubs.py
"""

import subprocess
import shutil
import sys
import re
from pathlib import Path


def enhance_core_stub(stub_path: Path) -> None:
    """Enhance the core.pyi stub file with explicit parameters for init method."""
    if not stub_path.exists():
        return
    
    content = stub_path.read_text()
    
    # Enhanced init method signature with all parameters
    enhanced_init = '''    @classmethod
    def init(cls, project_name: str | None = None, api_key: str | None = None, endpoint: str | None = None, objects_endpoint: str | None = None, spans_endpoint: str | None = None, metrics_endpoint: str | None = None, env: str | None = None, batch_size: int | None = None, batch_age: float | None = None, flush_interval: float | None = None, log_to_stdout: bool | None = None, stdout_log_level: str | None = None, debug_mode: bool | None = None, otel_format: bool | None = None, capture_stdout: bool | None = None, capture_python_logger: bool | None = None, python_logger_level: str | None = None, python_logger_name: str | None = None, code_snippet_enabled: bool | None = None, code_snippet_context_lines: int | None = None, code_snippet_max_frames: int | None = None, code_snippet_exclude_patterns: list[str] | None = None, install_signal_handlers: bool | None = None, local_server_enabled: bool | None = None, local_server_endpoint: str | None = None, local_server_service_name: str | None = None, custom_log_exporter: Any | None = None, custom_span_exporter: Any | None = None, custom_metrics_exporter: Any | None = None) -> None: ...'''
    
    # Replace the auto-generated init method with our enhanced version
    pattern = r'    @classmethod\s+def init\(cls, \*\*kwargs: Any\) -> None: \.\.\.'
    content = re.sub(pattern, enhanced_init, content)
    
    stub_path.write_text(content)
    print(f"Enhanced {stub_path} with explicit init() parameters")


def main():
    """Generate stub files for lumberjack_sdk."""
    print("Generating type stub files...")
    
    # Generate stubs to temporary location
    result = subprocess.run([
        "stubgen", "-p", "lumberjack_sdk", "-o", "."
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error generating stubs: {result.stderr}")
        sys.exit(1)
    
    print(f"Generated stubs for {result.stdout.strip()}")
    
    # Move .pyi files to src directory
    temp_dir = Path("lumberjack_sdk")
    src_dir = Path("src/lumberjack_sdk")
    
    if temp_dir.exists():
        # Copy all .pyi files
        for pyi_file in temp_dir.rglob("*.pyi"):
            relative_path = pyi_file.relative_to(temp_dir)
            target_path = src_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pyi_file, target_path)
            print(f"Updated {target_path}")
        
        # Clean up temporary directory
        shutil.rmtree(temp_dir)
        print("Cleaned up temporary files")
    
    # Apply enhancements to specific stub files
    core_stub = src_dir / "core.pyi"
    enhance_core_stub(core_stub)
    
    print("✅ Stub files generated successfully!")
    print("✅ Applied manual enhancements to preserve IDE support")
    print("\nNext steps:")
    print("1. Review the generated .pyi files")
    print("2. Test your IDE's autocomplete and type checking")
    print("3. Build and test the package")


if __name__ == "__main__":
    main()