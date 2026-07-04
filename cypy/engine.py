import sys
import json
import time
import os

# Top level imports for PyInstaller to detect dependencies
from cypy.core.providers import create_provider
from cypy.core.yolo_onnx import YOLOONNX
from cypy.core.translator import proses_satu_gambar

def get_env_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "..", "..", "..", ".env")
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")

def get_profile_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "..", "..", "..", "cypy_profile.json")
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cypy_profile.json")

def get_workspace_root():
    if getattr(sys, 'frozen', False):
        return os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", "..", ".."))
    else:
        return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

def get_model_path(filename):
    """Find a model file next to the executable (dev + release), falling back to assets/."""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "data", filename)
    else:
        return os.path.join(get_workspace_root(), "assets", filename)

# Redirect stdout to avoid breaking JSON-RPC
real_stdout = sys.stdout
class JSONRPCWriter:
    def __init__(self):
        self.buffer = ""
    def write(self, s):
        sys.stderr.write(s)
        self.buffer += s
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            if line:
                if "Translating" in line or "Loading" in line or "progress" in line.lower() or line.startswith("["):
                    send_rpc({"type": "progress", "message": line})
    def flush(self):
        sys.stderr.flush()

sys.stdout = JSONRPCWriter()

def send_rpc(msg_dict):
    real_stdout.write(json.dumps(msg_dict) + "\n")
    real_stdout.flush()

yolo_model = None

def get_config():
    env_vars = {}
    try:
        env_path = get_env_path()
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        env_vars[k.strip()] = v.strip().strip('"').strip("'")
    except:
        pass
        
    provider = env_vars.get("LLM_PROVIDER", "gemini").lower()
    model = env_vars.get(f"MODEL_{provider.upper()}", "")
    
    if not model:
        if provider == "gemini": model = "gemini-3.1-flash-lite"
        elif provider == "openai": model = "gpt-5.4"
        elif provider == "openrouter": model = "qwen/qwen2.5-vl-72b-instruct:free"
        elif provider == "zen": model = "minimax-m3-free"
        elif provider == "custom": model = "gpt-5.4-mini"

    api_keys = {
        "gemini": env_vars.get("GEMINI_API_KEY", ""),
        "openai": env_vars.get("OPENAI_API_KEY", ""),
        "openrouter": env_vars.get("OPENROUTER_API_KEY", ""),
        "zen": env_vars.get("ZEN_API_KEY", ""),
        "custom": env_vars.get("CUSTOM_API_KEY", "")
    }

    tweaks = {}
    try:
        prof_path = get_profile_path()
        if os.path.exists(prof_path):
            with open(prof_path, "r", encoding="utf-8") as f:
                tweaks = json.load(f)
    except:
        pass
        
    config = {
        "LLM_PROVIDER": provider,
        "MODEL": model,
        "API_KEYS": api_keys,
        "TWEAKS": tweaks
    }
    send_rpc({"type": "config", "data": config})

def save_config(payload):
    provider = payload.get("provider", "gemini")
    model = payload.get("model", "")
    api_key = payload.get("api_key", "")
    tweaks = payload.get("tweaks", {})
    
    env_path = get_env_path()
    
    env_key_map = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "zen": "ZEN_API_KEY",
        "custom": "CUSTOM_API_KEY"
    }
    env_key = env_key_map.get(provider, "GEMINI_API_KEY")
    
    existing = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            existing = f.readlines()
            
    found_prov = False
    for i, line in enumerate(existing):
        if line.startswith("LLM_PROVIDER="):
            existing[i] = f"LLM_PROVIDER={provider}\n"
            found_prov = True
            break
    if not found_prov:
        existing.insert(0, f"LLM_PROVIDER={provider}\n")
        
    model_key = f"MODEL_{provider.upper()}"
    found_mod = False
    for i, line in enumerate(existing):
        if line.startswith(f"{model_key}="):
            existing[i] = f"{model_key}={model}\n"
            found_mod = True
            break
    if not found_mod:
        existing.append(f"{model_key}={model}\n")
        
    if api_key:
        found_key = False
        for i, line in enumerate(existing):
            if line.startswith(f"{env_key}="):
                existing[i] = f'{env_key}="{api_key}"\n'
                found_key = True
                break
        if not found_key:
            existing.append(f'{env_key}="{api_key}"\n')
            
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(existing)
        
    try:
        with open(get_profile_path(), "w", encoding="utf-8") as f:
            json.dump(tweaks, f, indent=4)
    except Exception as e:
        pass

    send_rpc({"type": "info", "message": "Config saved successfully."})

def process_command(line):
    try:
        data = json.loads(line)
        action = data.get("action")
        payload = data.get("payload", {})
        
        if action == "get_config":
            get_config()
            
        elif action == "save_config":
            save_config(payload)
            
        elif action == "translate":
            image_path = payload.get("image_path")
            provider_name = payload.get("provider", "gemini")
            model = payload.get("model", "gemini-3.1-flash-lite")
            target_lang = payload.get("target_language", "Indonesian")
            
            if not os.path.isabs(image_path) and not os.path.exists(image_path):
                # Try to guess path if it's relative
                ws_root = get_workspace_root()
                image_path = os.path.join(ws_root, image_path)
            
            send_rpc({"type": "progress", "message": "Inisialisasi engine..."})
            
            global yolo_model
            if yolo_model is None:
                send_rpc({"type": "progress", "message": "Memuat model YOLOv8 ONNX..."})
                model_path = get_model_path("eyecyre.onnx")
                try:
                    yolo_model = YOLOONNX(model_path)
                except Exception as e:
                    send_rpc({"type": "error", "message": f"Gagal memuat YOLO: {e}"})
                    return
            
            # Load env vars to os.environ for create_provider
            env_path = get_env_path()
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line_env in f:
                        if "=" in line_env and not line_env.strip().startswith("#"):
                            k, v = line_env.strip().split("=", 1)
                            os.environ[k.strip()] = v.strip().strip('"').strip("'")
                            
            os.environ["LLM_PROVIDER"] = provider_name
            os.environ[f"MODEL_{provider_name.upper()}"] = model
            
            try:
                provider = create_provider(provider_name)
            except Exception as e:
                send_rpc({"type": "error", "message": f"Gagal membuat provider: {e}"})
                return
                
            try:
                if not os.path.exists(image_path):
                    send_rpc({"type": "error", "message": f"File tidak ditemukan: {image_path}"})
                    return
                
                res_path = proses_satu_gambar(image_path, yolo_model, provider, target_language=target_lang)
                if res_path:
                    # Return absolute path so Tauri can convert it to asset://
                    send_rpc({"type": "result", "status": "success", "output_image_path": os.path.abspath(res_path)})
                else:
                    send_rpc({"type": "error", "message": "Gagal memproses gambar (corrupt/unreadable)."})
            except Exception as e:
                send_rpc({"type": "error", "message": str(e)})
            
        elif action == "ping":
            send_rpc({"type": "pong"})
            
        else:
            send_rpc({"type": "error", "message": f"Aksi tidak dikenal: {action}"})
            
    except json.JSONDecodeError:
        send_rpc({"type": "error", "message": "JSON tidak valid"})
    except Exception as e:
        send_rpc({"type": "error", "message": str(e)})

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        
        line = line.strip()
        if line:
            process_command(line)

if __name__ == "__main__":
    main()
