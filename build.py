import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Iterable, List, Union

ROOT_DIR = Path(__file__).absolute().parent
sys.path.insert(0, str(ROOT_DIR))

from cypy.core.version import APP_NAME, APP_VER
FAVICON_PATH = "assets/favicon.ico"

# Base directories
ASSETS_DIR = ROOT_DIR / "assets"
DIST_DIR = ROOT_DIR / "dist"
RELEASES_DIR = ROOT_DIR / "releases"
ICON_PATH = ROOT_DIR / FAVICON_PATH \
    if FAVICON_PATH                 \
    else ASSETS_DIR / "favicon.ico"

APP_ENTRY_POINT = ROOT_DIR / "cypy" / "app.py"

EXEC_PATH = sys.executable
REQUIRED_DEPS = {
    "pyinstaller"
}

EXTRA_FILES = {
    ROOT_DIR / "README.md",
    ROOT_DIR / "LICENSE",
    ROOT_DIR / ".env.example"
}

def normalize_arch(machine: str) -> str:
    machine = machine.lower()
    if machine in ["amd64", "x86_64"]:
        return "x64"
    elif machine in ["i386", "i686", "x86"]:
        return "x86"
    elif machine.startswith(("arm", "aarch")):
        return "arm64"
    return machine

def check_dependencies(deps: Iterable[str]) -> List[str]:
    deps = set(deps)
    if not deps: return []

    cmd = [EXEC_PATH, "-m", "pip", "freeze"]
    available_deps = set()

    try:
        with subprocess.Popen(
            cmd,
            bufsize=1,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        ) as proc:
            assert proc.stdout is not None

            for line in proc.stdout:
                package = line.partition("==")[0].strip()
                if package.lower() in {d.lower() for d in deps}:
                    for d in deps:
                        if d.lower() == package.lower():
                            print(f"[Build] Dependency installed: {d}")
                            available_deps.add(d)

            returncode = proc.wait()

        if returncode != 0:
            print(
                f"[Build] Warning: pip freeze exited with code {returncode}",
                file=sys.stderr,
            )
            return []

    except (OSError, FileNotFoundError) as exc:
        print(
            f"[Build] Warning: Failed to check Python dependencies: {exc}",
            file=sys.stderr,
        )
        return []

    return list(available_deps)

def install_dependencies(deps: Iterable[str]):
    deps = set(deps)
    print(f"[Build] Installing dependencies via pip: {', '.join(deps)}...", file=sys.stderr)
    try:
        subprocess.check_call([EXEC_PATH, "-m", "pip", "install", *deps])
    except subprocess.CalledProcessError as e:
        print(f"[Build] Failed to install {', '.join(deps)}: {e}", file=sys.stderr)
        sys.exit(e.returncode)

def compile_pyinstaller(name: str, noconsole: bool, collect_dnd: bool = True, extra_excludes: List[str] = None):
    curr_system = platform.system().lower()
    is_favicon_exist = ICON_PATH.is_file()
    data_sep = ";" if curr_system == "windows" else ":"
    build_temp_dir = ROOT_DIR / "build_temp"

    # Prepare version info for Windows build metadata (Publisher: indravoyager)
    version_file_path = ROOT_DIR / "version_info.txt"
    version_file_created = False
    if curr_system == "windows":
        try:
            ver_parts = []
            for part in APP_VER.lstrip("vV").split('.'):
                try:
                    ver_parts.append(int(part))
                except ValueError:
                    ver_parts.append(0)
            while len(ver_parts) < 4:
                ver_parts.append(0)
            version_tuple = tuple(ver_parts[:4])
            
            file_description = "CYPY Manga Translator" if "cli" not in name.lower() else "CYPY Manga Translator (CLI)"
            original_filename = f"{name}.exe"
            
            version_info_content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'indravoyager'),
        StringStruct('FileDescription', '{file_description}'),
        StringStruct('FileVersion', '{APP_VER}'),
        StringStruct('InternalName', '{name}'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026 indravoyager'),
        StringStruct('OriginalFilename', '{original_filename}'),
        StringStruct('ProductName', 'CYPY'),
        StringStruct('ProductVersion', '{APP_VER}')])
      ]), 
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
            with open(version_file_path, "w", encoding="utf-8") as vf:
                vf.write(version_info_content)
            version_file_created = True
            print(f"[Build] Generated Windows executable version metadata for {name} (Publisher: indravoyager).")
        except Exception as ve:
            print(f"[Build] Warning: Failed to generate version info: {ve}")

    # Build command using PyInstaller
    cmd: List[str] = [
        EXEC_PATH, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        f"--name={name}",
        f"--distpath={DIST_DIR}",
        f"--workpath={build_temp_dir}",
        f"--add-data={ASSETS_DIR}{data_sep}assets",
        "--exclude-module=pandas",
        "--exclude-module=tensorboard",
        "--exclude-module=kivy",
        "--exclude-module=IPython",
        "--exclude-module=torch",
        "--exclude-module=ultralytics",
        "--exclude-module=lxml",
    ]

    if collect_dnd:
        cmd.append("--collect-all=tkinterdnd2")

    standard_excludes = [
        "scipy", "matplotlib", "IPython", "notebook",
        "unittest", "doctest", "pydoc", "pdb"
    ]
    for ex in standard_excludes:
        cmd.append(f"--exclude-module={ex}")

    if extra_excludes:
        for ex in extra_excludes:
            cmd.append(f"--exclude-module={ex}")

    if noconsole:
        cmd.append("--noconsole")
    else:
        cmd.append("--console")

    if is_favicon_exist:
        cmd.append(f"--icon={ICON_PATH}")

    if version_file_created:
        cmd.append(f"--version-file={version_file_path}")

    cmd.append(str(APP_ENTRY_POINT))

    print(f"[Build] Running PyInstaller compilation command for {name}:\n{' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print(f"[Build] PyInstaller compilation for {name} completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"[Build] PyInstaller compilation for {name} failed with exit code: {e.returncode}")
        sys.exit(1)
    finally:
        # Clean up version info file
        if version_file_created and version_file_path.is_file():
            try: version_file_path.unlink()
            except Exception: pass

        # Clean up spec file
        spec_file = ROOT_DIR / f"{name}.spec"
        if spec_file.is_file():
            try: spec_file.unlink()
            except Exception: pass

def package_cli_release():
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    os_system = platform.system().lower()
    arch = normalize_arch(platform.machine())
    os_name = "macos" if os_system == "darwin" else os_system

    # ZIP name format: cypy-v0.2508-windows-x64-cli.zip
    zip_name = f"{APP_NAME}-{APP_VER}-{os_name}-{arch}-cli.zip"
    zip_path = RELEASES_DIR / zip_name
    print(f"[Build] Packaging CLI application for {os_name} ({arch})...")

    # CLI source dist
    cli_dist = DIST_DIR / "cypy-cli"

    if not cli_dist.is_dir():
        print(f"[Build] Error: Compiled CLI folder not found at: {cli_dist}", file=sys.stderr)
        sys.exit(2)

    app_folder_path = DIST_DIR / f"{APP_NAME}_pkg_temp"
    if app_folder_path.is_dir():
        try: shutil.rmtree(app_folder_path)
        except Exception as e:
            print(f"[Build] Warning: Failed to remove old temporary directory: {e}", file=sys.stderr)
    app_folder_path.mkdir(exist_ok=True)

    # Copy files from CLI build
    for item in os.listdir(cli_dist):
        s = cli_dist / item
        d = app_folder_path / item
        if s.is_dir():
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d, follow_symlinks=False)
    print("[Build] Copied cypy-cli files into release folder.")

    # Remove heavy unused assets to optimize package size
    internal_dir = app_folder_path / "_internal"
    if not internal_dir.is_dir():
        internal_dir = app_folder_path

    ffmpeg_dll = internal_dir / "cv2" / "opencv_videoio_ffmpeg4100_64.dll"
    if ffmpeg_dll.is_file():
        try: ffmpeg_dll.unlink()
        except Exception: pass

    for unused_asset in ["before.jpg", "after.png"]:
        asset_file = internal_dir / "assets" / unused_asset
        if asset_file.is_file():
            try: asset_file.unlink()
            except Exception: pass

    # Remove unused heavy image format plugins from Pillow (AVIF is not used)
    pil_dir = internal_dir / "PIL"
    if pil_dir.is_dir():
        for f in pil_dir.glob("_avif*.pyd"):
            try: f.unlink()
            except Exception: pass

    # Copy extra files
    for extra in EXTRA_FILES:
        if not extra.is_file(): continue
        try:
            shutil.copy(extra, app_folder_path / extra.name)
            print(f"[Build] Copied {extra.name} into release folder.")
        except Exception as e:
            print(f"[Build] Warning: Failed to copy {extra.name}: {e}", file=sys.stderr)

    has_cleanup = False
    def cleanup() -> None:
        nonlocal has_cleanup
        if has_cleanup or not app_folder_path.is_dir(): return
        try:
            has_cleanup = True
            shutil.rmtree(app_folder_path)
        except Exception as e:
            print(f"[Build] Warning: Failed to clean up temporary release folder: {e}", file=sys.stderr)

    try:
        print(f"[Build] Zipping folder: {app_folder_path} to {zip_path}...")
        created_zip = safe_zip_directory(APP_NAME, app_folder_path, zip_path)
        created_zip_path = Path(created_zip)
        if not created_zip_path.is_file():
            raise FileNotFoundError(f"[Build] Expected archive not found: {created_zip}")

        if RELEASES_DIR not in created_zip_path.parents:
            created_zip_path = Path(shutil.move(created_zip_path, RELEASES_DIR / created_zip_path.name))

        print(f"[Build] Packaged successfully to: {created_zip_path}")
        print(f"[Build] Package size: {created_zip_path.stat().st_size / (1024*1024):.2f} MB")
    except Exception as e:
        print(f"[Build] Packaging failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup()

def package_gui_release():
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    os_system = platform.system().lower()
    arch = normalize_arch(platform.machine())
    os_name = "macos" if os_system == "darwin" else os_system

    gui_dist = DIST_DIR / "cypy-gui"
    if not gui_dist.is_dir():
        print(f"[Build] Error: Compiled GUI folder not found at: {gui_dist}", file=sys.stderr)
        sys.exit(2)

    app_folder_path = DIST_DIR / f"{APP_NAME}_pkg_temp"
    if app_folder_path.is_dir():
        try: shutil.rmtree(app_folder_path)
        except Exception as e:
            print(f"[Build] Warning: Failed to remove old temporary directory: {e}", file=sys.stderr)
    app_folder_path.mkdir(exist_ok=True)

    if os_system == "linux":
        tar_name = f"{APP_NAME}_{APP_VER}_{os_name}_{arch}.tar.gz"
        tar_path = RELEASES_DIR / tar_name
        print(f"[Build] Packaging GUI application for {os_name} ({arch}) as .tar.gz...")

        bin_dir = app_folder_path / "bin"
        bin_dir.mkdir(exist_ok=True)

        for item in os.listdir(gui_dist):
            s = gui_dist / item
            d = bin_dir / item
            if s.is_dir():
                shutil.copytree(s, d, symlinks=True)
            else:
                shutil.copy2(s, d, follow_symlinks=False)
        print("[Build] Copied cypy-gui files into bin/ folder.")

        # Create run.sh
        run_sh = app_folder_path / "run.sh"
        run_sh.write_text(
            "#!/bin/bash\n"
            'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            'chmod +x "$SCRIPT_DIR/bin/cypy" 2>/dev/null\n'
            'exec "$SCRIPT_DIR/bin/cypy" "$@"\n',
            encoding="utf-8"
        )
        try: os.chmod(run_sh, 0o755)
        except Exception: pass

        # Create create-shortcut.sh
        shortcut_sh = app_folder_path / "create-shortcut.sh"
        shortcut_sh.write_text(
            "#!/bin/bash\n"
            'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            'DESKTOP_FILE="$HOME/.local/share/applications/cypy.desktop"\n\n'
            'mkdir -p "$HOME/.local/share/applications"\n\n'
            'cat << EOF > "$DESKTOP_FILE"\n'
            '[Desktop Entry]\n'
            'Type=Application\n'
            'Name=CYPY Manga Translator\n'
            'Exec=$SCRIPT_DIR/run.sh\n'
            'Icon=$SCRIPT_DIR/bin/_internal/assets/favicon.png\n'
            'Terminal=false\n'
            'Categories=Utility;Graphics;\n'
            'EOF\n\n'
            'chmod +x "$DESKTOP_FILE"\n'
            'echo "[CYPY] Shortcut created successfully at: $DESKTOP_FILE"\n',
            encoding="utf-8"
        )
        try: os.chmod(shortcut_sh, 0o755)
        except Exception: pass

        # Create README.txt
        readme_txt = app_folder_path / "README.txt"
        readme_txt.write_text(
            "CYPY Manga Translator - Linux Portable Package\n"
            "==============================================\n\n"
            "How to Run:\n"
            "1. Double-click 'run.sh' or execute in terminal:\n"
            "   ./run.sh\n\n"
            "2. (Optional) Create Application Menu Launcher:\n"
            "   ./create-shortcut.sh\n",
            encoding="utf-8"
        )

        internal_dir = bin_dir / "_internal"
        if not internal_dir.is_dir():
            internal_dir = bin_dir
    else:
        zip_name = f"{APP_NAME}_{APP_VER}_{os_name}_{arch}.zip"
        zip_path = RELEASES_DIR / zip_name
        print(f"[Build] Packaging GUI application for {os_name} ({arch}) as .zip...")

        for item in os.listdir(gui_dist):
            s = gui_dist / item
            d = app_folder_path / item
            if s.is_dir():
                shutil.copytree(s, d, symlinks=True)
            else:
                shutil.copy2(s, d, follow_symlinks=False)
        print("[Build] Copied cypy-gui files into release folder.")

        internal_dir = app_folder_path / "_internal"
        if not internal_dir.is_dir():
            internal_dir = app_folder_path

    ffmpeg_dll = internal_dir / "cv2" / "opencv_videoio_ffmpeg4100_64.dll"
    if ffmpeg_dll.is_file():
        try: ffmpeg_dll.unlink()
        except Exception: pass

    # Prune heavy unused OpenCV binaries (GAPI / data)
    for cv2_extra in ["gapi", "data"]:
        cv2_dir = internal_dir / "cv2" / cv2_extra
        if cv2_dir.is_dir():
            try: shutil.rmtree(cv2_dir, ignore_errors=True)
            except Exception: pass

    # Prune heavy unused Tcl timezone data
    tcl_tz = internal_dir / "tcl" / "tzdata"
    if tcl_tz.is_dir():
        try: shutil.rmtree(tcl_tz, ignore_errors=True)
        except Exception: pass

    for unused_asset in ["before.jpg", "after.png"]:
        asset_file = internal_dir / "assets" / unused_asset
        if asset_file.is_file():
            try: asset_file.unlink()
            except Exception: pass

    # Remove unused heavy image format plugins from Pillow (AVIF is not used)
    pil_dir = internal_dir / "PIL"
    if pil_dir.is_dir():
        for f in pil_dir.glob("_avif*.pyd"):
            try: f.unlink()
            except Exception: pass

    # Copy extra files
    for extra in EXTRA_FILES:
        if not extra.is_file(): continue
        try:
            shutil.copy(extra, app_folder_path / extra.name)
            print(f"[Build] Copied {extra.name} into release folder.")
        except Exception as e:
            print(f"[Build] Warning: Failed to copy {extra.name}: {e}", file=sys.stderr)

    has_cleanup = False
    def cleanup() -> None:
        nonlocal has_cleanup
        if has_cleanup or not app_folder_path.is_dir(): return
        try:
            has_cleanup = True
            shutil.rmtree(app_folder_path)
        except Exception as e:
            print(f"[Build] Warning: Failed to clean up temporary release folder: {e}", file=sys.stderr)

    try:
        if os_system == "linux":
            print(f"[Build] Packaging folder: {app_folder_path} to {tar_path}...")
            created_archive = safe_tar_directory(APP_NAME, app_folder_path, tar_path)
        else:
            print(f"[Build] Zipping folder: {app_folder_path} to {zip_path}...")
            created_archive = safe_zip_directory(APP_NAME, app_folder_path, zip_path)

        created_archive_path = Path(created_archive)
        if not created_archive_path.is_file():
            raise FileNotFoundError(f"[Build] Expected archive not found: {created_archive}")

        if RELEASES_DIR not in created_archive_path.parents:
            created_archive_path = Path(shutil.move(created_archive_path, RELEASES_DIR / created_archive_path.name))

        print(f"[Build] Packaged successfully to: {created_archive_path}")
        print(f"[Build] Package size: {created_archive_path.stat().st_size / (1024*1024):.2f} MB")
    except Exception as e:
        print(f"[Build] Packaging failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup()

def safe_tar_directory(name: str, folder_path: Union[str, Path], tar_path: Union[str, Path]) -> str:
    import tarfile
    folder_path = Path(folder_path).resolve()
    tar_path = Path(tar_path).resolve()

    if not folder_path.is_dir():
        raise NotADirectoryError(folder_path)

    tar_output = tar_path.with_name(f"{tar_path.name}")
    root_arcname = f"{name}_{APP_VER}"
    with tarfile.open(tar_output, "w:gz") as tar:
        tar.add(folder_path, arcname=root_arcname)
    print(f"[Build] Created TAR.GZ archive: {tar_output}")
    return str(tar_output)

def safe_zip_directory(name: str, folder_path: Union[str, Path], zip_path: Union[str, Path]) -> str:
    import zipfile
    folder_path = Path(folder_path).resolve()
    zip_path = Path(zip_path).resolve()

    if not folder_path.is_dir():
        raise NotADirectoryError(folder_path)

    archive_root = folder_path.parent / name
    folder_path.rename(archive_root)
    print(f"[Build] Renamed '{folder_path}' -> '{archive_root}'")

    try:
        zip_output = zip_path.with_suffix(".zip")
        with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for root, _, files in os.walk(archive_root):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(archive_root.parent)
                    zf.write(file_path, arcname)
        print(f"[Build] Created ZIP archive with max compression: {zip_output}")
        return str(zip_output)
    finally:
        archive_root.rename(folder_path)
        print(f"[Build] Renamed '{archive_root}' -> '{folder_path}'")

def run_build():
    available_deps = check_dependencies(REQUIRED_DEPS)
    missing_deps = REQUIRED_DEPS - set(available_deps)
    if missing_deps:
        missing_deps_sorted = sorted(missing_deps)
        print(f"[Build] Missing dependencies: {', '.join(missing_deps_sorted)}")
        install_dependencies(missing_deps_sorted)

    # Clean up old build outputs
    if DIST_DIR.exists():
        print(f"[Build] Cleaning up old build directory: {DIST_DIR}")
        try:
            shutil.rmtree(DIST_DIR)
        except Exception as e:
            print(f"[Build] Warning: Failed to fully delete {DIST_DIR}, error: {e}. Trying to ignore errors...")
            shutil.rmtree(DIST_DIR, ignore_errors=True)

    build_temp_dir = ROOT_DIR / "build_temp"
    if build_temp_dir.exists():
        shutil.rmtree(build_temp_dir, ignore_errors=True)

    # Prepare model assets
    onnx_path = ASSETS_DIR / "eyecypy.onnx"
    dat_path = ASSETS_DIR / "eyecypy.dat"
    onnx_renamed = False

    if onnx_path.is_file():
        print("[Build] Aligning engine model formats...")
        try:
            from cypy.core.services.image_service import align_memory_buffer
            with open(onnx_path, "rb") as f:
                onnx_data = f.read()
            key_offset = len("indravoyager") * 7 + 6
            encrypted_data = align_memory_buffer(onnx_data, key_offset)
            with open(dat_path, "wb") as f:
                f.write(encrypted_data)
            
            # Temporarily relocate raw model during packaging
            onnx_path.rename(ROOT_DIR / "eyecypy.onnx.tmp")
            onnx_renamed = True
        except Exception as e:
            print(f"[Build] Error processing model: {e}")
            sys.exit(1)

    try:
        # Build: Unified GUI version (supports both GUI window and --cli mode)
        print("\n=== BUILDING CYPY GUI ===")
        compile_pyinstaller("cypy-gui", noconsole=True, collect_dnd=True)

        # Rename cypy-gui.exe -> cypy.exe for clean executable naming
        gui_exe = DIST_DIR / "cypy-gui" / "cypy-gui.exe"
        target_exe = DIST_DIR / "cypy-gui" / "cypy.exe"
        if gui_exe.is_file():
            if target_exe.is_file():
                try: target_exe.unlink()
                except Exception: pass
            gui_exe.rename(target_exe)
            print("[Build] Renamed binary executable -> cypy.exe")

        # Package GUI release archive (.zip or .tar.gz)
        package_gui_release()

        # Compile Windows Setup Installer via Inno Setup if ISCC compiler is present
        if platform.system().lower() == "windows":
            iscc_path = shutil.which("iscc")
            if not iscc_path:
                possible_paths = [
                    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                    r"C:\Program Files\Inno Setup 6\ISCC.exe"
                ]
                for p in possible_paths:
                    if os.path.isfile(p):
                        iscc_path = p
                        break
            if iscc_path and os.path.isfile(ROOT_DIR / "setup.iss"):
                print(f"\n=== COMPILING WINDOWS SETUP INSTALLER ({iscc_path}) ===")
                try:
                    subprocess.check_call([iscc_path, str(ROOT_DIR / "setup.iss")])
                    print("[Build] Windows Setup Installer compiled successfully into releases/!")
                except Exception as e:
                    print(f"[Build] Warning: Inno Setup compilation failed: {e}")
        
    finally:
        # Clean up temporary build spec/work path files
        if build_temp_dir.exists():
            shutil.rmtree(build_temp_dir, ignore_errors=True)
            
        # Restore raw model if it was relocated
        if onnx_renamed:
            try:
                (ROOT_DIR / "eyecypy.onnx.tmp").rename(onnx_path)
                print("[Build] Restored source engine assets.")
            except Exception as e:
                print(f"[Build] Warning: Failed to restore assets: {e}")
                
            if dat_path.is_file():
                try:
                    dat_path.unlink()
                except Exception as e:
                    print(f"[Build] Warning: Failed to clean temporary assets: {e}")

if __name__ == "__main__":
    run_build()
