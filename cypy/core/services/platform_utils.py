"""
cypy/core/services/platform_utils.py
✦ Platform Utilities — OS-specific helpers~ ♪ ✦
"""
import os
import sys
import subprocess

import cypy.core.config as config


def create_shortcut_if_first_run():
    """
    Automatically creates a Windows desktop shortcut on the first run of the application.
    Does nothing on non-Windows platforms or in development mode.
    """
    if sys.platform != "win32":
        return

    if not getattr(sys, 'frozen', False):
        return

    base_path = os.path.dirname(sys.executable)
    cache_dir = os.path.join(config.DATA_DIR, "cypy_cache")
    os.makedirs(cache_dir, exist_ok=True)

    flag_file = os.path.join(cache_dir, ".shortcut_created")
    if os.path.exists(flag_file):
        return

    try:
        exe_path = sys.executable
        working_dir = base_path

        # PowerShell script to create shortcut pointing to the exe and setting its icon
        ps_cmd = (
            f"$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut(([Environment]::GetFolderPath('Desktop') + '\\\\cypy.lnk')); "
            f"$Shortcut.TargetPath = '{exe_path}'; "
            f"$Shortcut.WorkingDirectory = '{working_dir}'; "
            f"$Shortcut.IconLocation = '{exe_path}'; "
            f"$Shortcut.Save()"
        )

        creation_flags = 0x08000000  # CREATE_NO_WINDOW
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            creationflags=creation_flags,
            check=True
        )

        with open(flag_file, "w") as f:
            f.write("created")

        print("[Utils] Desktop shortcut successfully created.")
    except Exception as e:
        print(f"[Utils] Failed to create desktop shortcut: {e}")
