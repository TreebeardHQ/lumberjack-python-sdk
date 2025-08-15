"""
CLI commands for Lumberjack Local Development Server.

Provides 'lumberjack serve' and 'lumberjack claude init' commands.
"""
import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from ..internal_utils.fallback_logger import fallback_logger


def find_available_port(start_port: int = 8080, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port.
    
    Args:
        start_port: Port to start checking from
        max_attempts: Maximum number of ports to try
        
    Returns:
        Available port number
        
    Raises:
        RuntimeError: If no available port found
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")


def serve_command(args: argparse.Namespace) -> None:
    """Handle the 'serve' command to start the local development server."""
    try:
        # Check if local-server dependencies are available
        try:
            from .server import start_server
            from .service_discovery import check_existing_server, check_port_availability
        except ImportError as e:
            print("❌ Local server dependencies not installed.")
            print("Install with: pip install 'lumberjack_sdk[local-server]'")
            sys.exit(1)
        
        # Check if another server is already running and provide helpful message
        existing_server = check_existing_server()
        if existing_server:
            print("❌ Another Lumberjack server is already running!")
            print(f"   PID: {existing_server.pid}")
            print(f"   Server URL: http://{existing_server.server_url}")
            print(f"   GRPC Port: {existing_server.grpc_port}")
            print(f"   Last heartbeat: {existing_server.time_since_heartbeat():.1f}s ago")
            print("\n💡 To connect to the existing server, point your SDK to:")
            host = existing_server.server_url.split(':')[0] if ':' in existing_server.server_url else existing_server.server_url
            print(f"   local_server_endpoint=\"{host}:{existing_server.grpc_port}\"")
            sys.exit(1)
        
        # Check if GRPC port 4317 is available
        port_error = check_port_availability(4317)
        if port_error:
            print(f"❌ Cannot start GRPC collector: {port_error}")
            print("💡 Please stop the process using port 4317 and try again.")
            sys.exit(1)
        
        # Determine port
        port = args.port
        if not port:
            try:
                port = find_available_port(8080)
                print(f"🔍 Auto-detected available port: {port}")
            except RuntimeError as e:
                print(f"❌ {e}")
                sys.exit(1)
        
        # Validate database path if provided
        db_path = args.db_path
        if db_path:
            db_path = os.path.abspath(db_path)
            db_dir = os.path.dirname(db_path)
            
            # Create directory if it doesn't exist
            if not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir)
                    print(f"📁 Created database directory: {db_dir}")
                except OSError as e:
                    print(f"❌ Failed to create database directory: {e}")
                    sys.exit(1)
        
        # Start the server
        print("🌲 Starting Lumberjack Local Development Server...")
        print(f"📊 Database: {'In-memory' if not db_path else db_path}")
        print(f"🔗 Web UI: http://127.0.0.1:{port}")
        print(f"🔌 GRPC Collector: localhost:4317")
        print("Press Ctrl+C to stop")
        
        start_server(
            host="127.0.0.1",
            port=port,
            db_path=db_path,
            open_browser=not args.no_browser,
            log_level="info" if args.verbose else "warning"
        )
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down Lumberjack Local Server...")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def claude_install_command(args: argparse.Namespace) -> None:
    """Handle the 'claude install' command to instrument the SDK with Claude's help."""
    try:
        import subprocess
        from pathlib import Path
        
        print("🤖 Preparing to instrument your application with Lumberjack SDK...")
        
        # Read the installation instructions
        instructions_path = Path(__file__).parent / "INSTALL_INSTRUCTIONS.md"
        if not instructions_path.exists():
            print("❌ Installation instructions file not found.")
            sys.exit(1)
        
        with open(instructions_path, 'r') as f:
            instructions = f.read()
        
        # Build the prompt for Claude
        prompt = f"""Please help me instrument my Python application with the Lumberjack SDK for local log collection.

{instructions}

Please analyze my codebase and:
1. Detect which web framework I'm using (Flask, FastAPI, Django, or none)
2. Find the appropriate main application file
3. Add the Lumberjack SDK initialization code with local_mode=True
4. Use a descriptive service_name based on my project
5. Ensure no API key is configured (we're using local mode)
6. Add lumberjack-sdk[local-server] to my dependencies if not already present

Make the necessary changes to properly instrument my application for local log collection."""

        # Find claude command
        claude_cmd = None
        possible_claude_paths = [
            "claude",  # In PATH
            os.path.expanduser("~/.claude/local/claude"),  # Claude Code local install
            "/usr/local/bin/claude",
            os.path.expanduser("~/.local/bin/claude"),
            "/opt/homebrew/bin/claude",
        ]
        
        for cmd in possible_claude_paths:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, check=True)
                claude_cmd = cmd
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        if not claude_cmd:
            print("❌ Claude Code CLI not found. Make sure Claude Code is installed.")
            print("Install from: https://claude.ai/download")
            sys.exit(1)
        
        print("📝 Launching Claude Code to instrument your application...")
        print("\n" + "="*60)
        print("Claude will analyze your code and add the Lumberjack SDK.")
        print("Please review the changes before accepting them.")
        print("="*60 + "\n")
        
        # Launch Claude with the prompt
        if args.dry_run:
            print("🔍 Dry run mode - here's the prompt that would be sent to Claude:\n")
            print(prompt)
        else:
            # Use subprocess to run claude with the prompt
            result = subprocess.run(
                [claude_cmd],
                input=prompt,
                text=True,
                capture_output=False  # Let Claude run interactively
            )
            
            if result.returncode == 0:
                print("\n✅ Claude has finished analyzing your code.")
                print("\n📋 Next steps:")
                print("1. Review the changes Claude made")
                print("2. Start the Lumberjack server: lumberjack serve")
                print("3. Run your application")
                print("4. View logs at http://localhost:8080")
            else:
                print("\n❌ Claude exited with an error.")
                sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error running Claude install: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def claude_remove_command(args: argparse.Namespace) -> None:
    """Handle the 'claude remove' command to remove MCP integration."""
    try:
        import subprocess
        print("🤖 Removing Lumberjack MCP integration from Claude Code...")
        
        # Try to find claude command in common locations
        claude_cmd = None
        possible_claude_paths = [
            "claude",  # In PATH
            os.path.expanduser("~/.claude/local/claude"),  # Claude Code local install
            "/usr/local/bin/claude",
            os.path.expanduser("~/.local/bin/claude"),
            "/opt/homebrew/bin/claude",
        ]
        
        for cmd in possible_claude_paths:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, check=True)
                claude_cmd = cmd
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        if not claude_cmd:
            print("❌ Claude Code CLI not found. Make sure Claude Code is installed.")
            print("Install from: https://claude.ai/download")
            sys.exit(1)
        
        # Remove the MCP server
        result = subprocess.run(
            [claude_cmd, "mcp", "remove", "lumberjack"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            if "not found" in result.stderr.lower():
                print("ℹ️  Lumberjack MCP server was not configured.")
            else:
                print(f"❌ Failed to remove MCP server: {result.stderr}")
                sys.exit(1)
        else:
            print("✅ Successfully removed Lumberjack MCP server from Claude Code!")
            print("\n📋 To re-add the MCP server later, run: lumberjack claude init")
        
    except Exception as e:
        print(f"❌ Error removing MCP server: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def claude_init_command(args: argparse.Namespace) -> None:
    """Handle the 'claude init' command to setup MCP integration."""
    try:
        import subprocess
        print("🤖 Setting up Claude Code MCP integration...")
        
        # Check if lumberjack-mcp command is available
        try:
            subprocess.run(["which", "lumberjack-mcp"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("❌ lumberjack-mcp command not found.")
            print("Make sure you've installed lumberjack with: pip install 'lumberjack_sdk[local-server]'")
            sys.exit(1)
        
        # Use claude mcp add command
        try:
            # Try to find claude command in common locations
            claude_cmd = None
            possible_claude_paths = [
                "claude",  # In PATH
                os.path.expanduser("~/.claude/local/claude"),  # Claude Code local install
                "/usr/local/bin/claude",
                os.path.expanduser("~/.local/bin/claude"),
                "/opt/homebrew/bin/claude",
            ]
            
            for cmd in possible_claude_paths:
                try:
                    subprocess.run([cmd, "--version"], capture_output=True, check=True)
                    claude_cmd = cmd
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            if not claude_cmd:
                print("❌ Claude Code CLI not found. Make sure Claude Code is installed.")
                print("Install from: https://claude.ai/download")
                sys.exit(1)
            
            result = subprocess.run(
                [claude_cmd, "mcp", "add", "lumberjack", "lumberjack-mcp"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                if "already exists" in result.stderr:
                    print("ℹ️  Lumberjack MCP server already configured.")
                else:
                    print(f"❌ Failed to add MCP server: {result.stderr}")
                    sys.exit(1)
            else:
                print("✅ Successfully added Lumberjack MCP server to Claude Code!")
            
        except Exception as e:
            print(f"❌ Error setting up MCP server: {e}")
            sys.exit(1)
        
        # Check status
        if claude_cmd:
            result = subprocess.run(
                [claude_cmd, "mcp", "list"],
                capture_output=True,
                text=True
            )
            
            if "lumberjack" in result.stdout and "✓" in result.stdout:
                print("✅ MCP server is connected and ready!")
            else:
                print("⚠️  MCP server added but not yet connected.")
                print("You may need to restart Claude Code or start a new session.")
        
        print("\n📋 Next steps:")
        print("1. Start the local server: lumberjack serve")
        print("2. Use Claude Code to interact with your logs!")
        
        # Show available tools
        print("\n🛠️  Available MCP tools:")
        print("  • recent_logs - Get recent logs (filter by service/level)")
        print("  • search_logs - Search logs by message or trace ID")
        print("  • list_services - List all services with log counts")
        print("  • start_server - Start the Lumberjack server")
        
        print("\n💡 Example things to ask Claude Code:")
        print("  • 'Show me the recent error logs'")
        print("  • 'Search for timeout in the logs'")
        print("  • 'List all services'")
        print("  • 'Find logs with trace ID abc123'")
        
    except Exception as e:
        print(f"❌ Failed to setup Claude Code integration: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="lumberjack",
        description="Lumberjack Local Development Server CLI"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands"
    )
    
    # Serve command
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the local development server"
    )
    serve_parser.add_argument(
        "--port", "-p",
        type=int,
        help="Port to serve on (default: auto-detect from 8080)"
    )
    serve_parser.add_argument(
        "--db-path",
        type=str,
        help="Path to SQLite database file (default: in-memory)"
    )
    serve_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser"
    )
    
    # Claude init command
    claude_parser = subparsers.add_parser(
        "claude",
        help="Claude Code integration commands"
    )
    claude_subparsers = claude_parser.add_subparsers(
        dest="claude_command",
        help="Claude Code commands"
    )
    
    init_parser = claude_subparsers.add_parser(
        "init",
        help="Setup MCP integration with Claude Code"
    )
    init_parser.add_argument(
        "--config-path",
        type=str,
        help="Path to Claude Code config file (auto-detected if not provided)"
    )
    
    install_parser = claude_subparsers.add_parser(
        "install",
        help="Use Claude to instrument your app with Lumberjack SDK"
    )
    install_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the prompt without running Claude"
    )
    
    remove_parser = claude_subparsers.add_parser(
        "remove",
        help="Remove MCP integration from Claude Code"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Handle commands
    if args.command == "serve":
        serve_command(args)
    elif args.command == "claude":
        if args.claude_command == "init":
            claude_init_command(args)
        elif args.claude_command == "install":
            claude_install_command(args)
        elif args.claude_command == "remove":
            claude_remove_command(args)
        else:
            claude_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()