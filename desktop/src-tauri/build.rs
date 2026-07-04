use std::path::PathBuf;

fn main() {
    tauri_build::build();

    // Resolve the target/<profile>/ directory from OUT_DIR (which is
    // target/<profile>/build/<pkg>/out/).  We go up 3 ancestors.
    let out_dir = std::env::var("OUT_DIR").unwrap_or_default();
    let target_dir = PathBuf::from(&out_dir)
        .ancestors()
        .nth(3)
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from(&out_dir));

    // --- Copy sidecar binary ---
    let sidecar_name = "cypy_engine-x86_64-pc-windows-msvc.exe";
    let src_bin = PathBuf::from("bin").join(sidecar_name);
    let dst_bin = target_dir.join(sidecar_name);
    if src_bin.exists() {
        if let Err(e) = std::fs::copy(&src_bin, &dst_bin) {
            eprintln!("cargo:warning=Failed to copy sidecar: {}", e);
        } else {
            println!("cargo:warning=Copied sidecar to {}", dst_bin.display());
        }
    } else {
        eprintln!("cargo:warning=Sidecar not found at {}", src_bin.display());
    }

    // --- Copy model data next to the sidecar (inside data/) ---
    let data_src = PathBuf::from("bin").join("data");
    let data_dst = target_dir.join("data");
    let data_dst_root = PathBuf::from("data"); // Copy to src-tauri/data for tauri dev
    
    if data_src.exists() {
        if let Err(e) = std::fs::create_dir_all(&data_dst) {
            eprintln!("cargo:warning=Failed to create data dir in target: {}", e);
        }
        if let Err(e) = std::fs::create_dir_all(&data_dst_root) {
            eprintln!("cargo:warning=Failed to create data dir in root: {}", e);
        }
        
        for entry in std::fs::read_dir(&data_src).unwrap_or_else(|_| std::fs::read_dir(".").unwrap()) {
            if let Ok(entry) = entry {
                let src_file = entry.path();
                let file_name = entry.file_name();
                
                let dst_file_target = data_dst.join(&file_name);
                if let Err(e) = std::fs::copy(&src_file, &dst_file_target) {
                    eprintln!("cargo:warning=Failed to copy data file to target: {}", e);
                }
                
                let dst_file_root = data_dst_root.join(&file_name);
                if let Err(e) = std::fs::copy(&src_file, &dst_file_root) {
                    eprintln!("cargo:warning=Failed to copy data file to root: {}", e);
                } else {
                    println!("cargo:warning=Copied data file to {}", dst_file_root.display());
                }
            }
        }
    }

    println!("cargo:rerun-if-changed=bin/{}", sidecar_name);
    println!("cargo:rerun-if-changed=bin/data/");
}
