import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).absolute().parent.parent
ENGINE_SCRIPT = ROOT_DIR / "cypy" / "engine.py"

# Tauri expects a specific target suffix for sidecars.
# Assuming 64-bit Windows:
TARGET_TRIPLE = "x86_64-pc-windows-msvc"
OUTPUT_NAME = f"cypy_engine-{TARGET_TRIPLE}.exe"

def build_engine():
    print(f"Building {ENGINE_SCRIPT} with Nuitka...")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--enable-plugin=numpy",
        f"--output-filename={OUTPUT_NAME}",
        f"--output-dir={ROOT_DIR / 'desktop' / 'src-tauri' / 'bin'}",
        str(ENGINE_SCRIPT)
    ]
    
    # Ensure bin directory exists
    bin_dir = ROOT_DIR / 'desktop' / 'src-tauri' / 'bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully built sidecar to {bin_dir / OUTPUT_NAME}")
    except subprocess.CalledProcessError as e:
        print(f"Error during Nuitka compilation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_engine()
