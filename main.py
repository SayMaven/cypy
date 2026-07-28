import sys
import traceback
import os

# Ensure the app starts in GUI mode on Android
if '--gui' not in sys.argv:
    sys.argv.append('--gui')


def _write_crash_log(tb_text, path):
    """Write crash log to a specific path. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("CYPY Start Crash Log\n")
            f.write("====================\n")
            f.write(tb_text)
        return True
    except Exception:
        return False


def log_crash(tb_text):
    """Attempt to write crash log to multiple fallback locations."""
    # Try current directory first
    if _write_crash_log(tb_text, "cypy_crash.txt"):
        return

    # Fallback to LOCALAPPDATA
    appdata = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "cypy"
    )
    if _write_crash_log(tb_text, os.path.join(appdata, "cypy_crash.txt")):
        return

    # On Android, try public external app files directory
    try:
        package_name = "org.indravoyager.cypy"
        public_dir = f"/storage/emulated/0/Android/data/{package_name}/files"
        if os.path.exists(public_dir):
            _write_crash_log(tb_text, os.path.join(public_dir, "cypy_crash.txt"))
    except Exception:
        pass


try:
    from cypy.app import main
    if __name__ == '__main__':
        main()
except Exception as e:
    log_crash(traceback.format_exc())
    raise
