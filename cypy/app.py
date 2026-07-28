"""
cypy/app.py
✦ Application Entry Point ✦

Thin dispatcher that routes to GUI or CLI mode based on arguments.
All heavy logic lives in cypy.cli.controller and cypy.gui.window.
"""
import os
import sys
import time

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


def main():
    """Main entry point for the cypy application."""
    # Detect launch mode based on executable name or arguments
    exe_name = os.path.basename(sys.argv[0]).lower()

    # Run in CLI mode if '--cli' is specified or the executable name contains 'cli'
    # Otherwise, default to GUI mode
    is_cli_mode = "--cli" in sys.argv or "cli" in exe_name

    if not is_cli_mode:
        from cypy.gui import main as gui_main
        gui_main()
        return

    from cypy.cli.controller import run_cli
    run_cli()


if __name__ == "__main__":
    main()