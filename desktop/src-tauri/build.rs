use std::path::PathBuf;

fn main() {
    tauri_build::build();

    // Copy the sidecar binary into the target directory so Tauri can find it
    // during `tauri dev` (dev mode looks for sidecars next to the running binary,
    // which is target/<profile>/, not the bin/ folder used only for release bundles).
    let out_dir = std::env::var("OUT_DIR").unwrap_or_default();
    // OUT_DIR is like .../target/debug/build/<pkg>/out  — go up 3 levels
    let target_dir = PathBuf::from(&out_dir)
        .ancestors()
        .nth(3)
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from(&out_dir));

    let sidecar_name = "cypy_engine-x86_64-pc-windows-msvc.exe";
    let src = PathBuf::from("bin").join(sidecar_name);
    let dst = target_dir.join(sidecar_name);

    if src.exists() {
        if let Err(e) = std::fs::copy(&src, &dst) {
            eprintln!("cargo:warning=Failed to copy sidecar: {}", e);
        } else {
            println!("cargo:warning=Copied sidecar to {}", dst.display());
        }
    } else {
        eprintln!("cargo:warning=Sidecar not found at {}", src.display());
    }

    // Re-run this build script whenever the sidecar changes
    println!("cargo:rerun-if-changed=bin/{}", sidecar_name);
}
