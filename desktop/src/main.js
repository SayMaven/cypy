// Use global Tauri API because this is a vanilla JS setup (no Vite bundler)
const Command = window.__TAURI_PLUGIN_SHELL__?.Command || window.__TAURI__?.shell?.Command || {
  sidecar: () => { 
    alert("Tauri API not found! __TAURI_PLUGIN_SHELL__ is " + typeof window.__TAURI_PLUGIN_SHELL__);
    throw new Error("Tauri API not found"); 
  }
};


// --- UI Elements ---
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const previewSingle = document.getElementById('preview-single');
const imgOriginal = document.getElementById('image-original');
const imgTranslated = document.getElementById('image-translated');
const loadingOverlay = document.getElementById('loading-overlay');
const statusText = document.getElementById('status-text');
const translateBtn = document.getElementById('translate-btn');
const galleryPanel = document.getElementById('gallery-panel');
const changeImageBtn = document.getElementById('change-image-btn');

// Settings Elements
const providerSelect = document.getElementById('provider');
const modelInput = document.getElementById('model');
const langSelect = document.getElementById('language-select');
const langCustom = document.getElementById('language-custom');
const modelDocsBtn = document.getElementById('model-docs-btn');

// Modal Elements
const settingsModal = document.getElementById('settings-modal');
const settingsBtn = document.getElementById('settings-btn');
const closeModalBtn = document.getElementById('close-modal-btn');
const saveConfigBtn = document.getElementById('save-config-btn');
const apiKeyInput = document.getElementById('api-key');
const apiKeyLabel = document.getElementById('api-key-label');
const toggleApiKeyBtn = document.getElementById('toggle-api-key-btn');

// Tweak Params
const sfxMode = document.getElementById('sfx_mode');
const patchGepeng = document.getElementById('patch_gepeng');
const padX = document.getElementById('pad_x');
const padY = document.getElementById('pad_y');
const skala = document.getElementById('skala_potongan');
const minPad = document.getElementById('min_pad');
const maskMargin = document.getElementById('mask_margin');

const docLinks = {
  gemini: 'https://ai.google.dev/gemini-api/docs/models?hl=id',
  openai: 'https://platform.openai.com/docs/models',
  openrouter: 'https://openrouter.ai/models',
  zen: 'https://opencode.ai/models',
  custom: '#'
};

// State
let filesToProcess = [];
let currentProcessIndex = 0;

// --- Event Listeners ---

// Update Range Labels
const valMap = {
  'pad_x': 'val_pad_x',
  'pad_y': 'val_pad_y',
  'skala_potongan': 'val_skala',
  'min_pad': 'val_min_pad',
  'mask_margin': 'val_mask'
};

Object.keys(valMap).forEach(id => {
  const el = document.getElementById(id);
  const val = document.getElementById(valMap[id]);
  if(el && val) {
    el.addEventListener('input', () => { val.textContent = el.value; });
  }
});

const providerNames = {
  gemini: "Google Gemini",
  openai: "OpenAI",
  openrouter: "OpenRouter",
  zen: "Zen (opencode.ai)",
  custom: "Custom Provider"
};

const defaultModels = {
  gemini: 'gemini-3.1-flash-lite',
  openai: 'gpt-5.4',
  openrouter: 'qwen/qwen2.5-vl-72b-instruct:free',
  zen: 'minimax-m3-free',
  custom: ''
};

// Cached state for API keys
let cachedApiKeys = { gemini: '', openai: '', openrouter: '', zen: '', custom: '' };

function updateApiKeyLabel() {
  if (apiKeyLabel) {
    apiKeyLabel.textContent = `${providerNames[providerSelect.value]} API Key (Empty to use .env)`;
  }
  if (apiKeyInput) {
    apiKeyInput.value = cachedApiKeys[providerSelect.value] || '';
  }
}

providerSelect.addEventListener('change', () => {
  const link = docLinks[providerSelect.value];
  modelDocsBtn.style.opacity = link !== '#' ? '1' : '0.3';
  updateApiKeyLabel();
  
  // Auto-switch model
  if (modelInput) {
    modelInput.value = defaultModels[providerSelect.value] || '';
  }
});

if (toggleApiKeyBtn) {
  toggleApiKeyBtn.addEventListener('click', () => {
    if (apiKeyInput.type === 'password') {
      apiKeyInput.type = 'text';
    } else {
      apiKeyInput.type = 'password';
    }
  });
}

// Call initially
updateApiKeyLabel();

modelDocsBtn.addEventListener('click', (e) => {
  e.preventDefault();
  const link = docLinks[providerSelect.value];
  if(link !== '#') {
    if (window.__TAURI__?.core?.invoke) {
      window.__TAURI__.core.invoke('plugin:opener|open_url', { url: link });
    } else {
      const a = document.createElement('a');
      a.href = link;
      a.target = "_blank";
      a.click();
    }
  }
});

langSelect.addEventListener('change', () => {
  if (langSelect.value === 'custom') {
    langCustom.classList.remove('hidden');
  } else {
    langCustom.classList.add('hidden');
  }
});

// Modal Logic
settingsBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));
closeModalBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));

async function openDialog() {
  try {
    if (window.__TAURI__?.core?.invoke) {
      const selected = await window.__TAURI__.core.invoke('plugin:dialog|open', {
        options: {
          multiple: true,
          filters: [{ name: 'Supported Files', extensions: ['png', 'jpg', 'jpeg', 'webp', 'cbz', 'cbr', 'pdf', 'zip', 'rar'] }]
        }
      });
      if (selected) {
        const paths = Array.isArray(selected) ? selected : [selected];
        handleTauriFiles(paths);
      }
    } else {
      alert("Tauri API not found! Use Native App to browse files.");
    }
  } catch (e) {
    console.error(e);
  }
}

dropZone.addEventListener('click', openDialog);
if (changeImageBtn) {
  changeImageBtn.addEventListener('click', openDialog);
}

// Native Tauri Drag and Drop
if (window.__TAURI__?.event?.listen) {
  window.__TAURI__.event.listen('tauri://drop', (event) => {
    if (event.payload && event.payload.paths) {
      handleTauriFiles(event.payload.paths);
    }
  });
}

dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  // HTML5 drop fallback
  if (e.dataTransfer && e.dataTransfer.files.length > 0 && !window.__TAURI__) {
      alert("Please use the desktop app version for drag and drop to work properly.");
  }
});

let translatedPaths = {};

// ... (in handleTauriFiles function)
function handleTauriFiles(paths) {
  if (paths.length === 0) return;
  
  filesToProcess = paths;
  currentProcessIndex = 0;
  translatedPaths = {};
  
  dropZone.classList.add('hidden');
  previewSingle.classList.remove('hidden');
  translateBtn.disabled = false;
// ...
  
  if (paths.length > 1) {
    // Batch Mode
    galleryPanel.classList.remove('hidden');
    galleryPanel.innerHTML = '';
    
    paths.forEach(async (path, idx) => {
      const img = document.createElement('img');
      img.className = 'thumb' + (idx === 0 ? ' active' : '');
      img.id = `thumb-${idx}`;
      img.title = path.split(/[\/\\]/).pop(); // show filename on hover
      
      img.addEventListener('click', () => {
        document.querySelectorAll('.thumb').forEach(el => el.classList.remove('active'));
        img.classList.add('active');
        setPreviewImage(idx);
      });
      
      try {
        const ext = path.split('.').pop().toLowerCase();
        const isImage = ['png', 'jpg', 'jpeg', 'webp', 'bmp'].includes(ext);
        
        if (isImage) {
          const fileData = await window.__TAURI__.core.invoke('plugin:fs|read_file', { path });
          const blob = new Blob([new Uint8Array(fileData)]);
          img.src = URL.createObjectURL(blob);
        } else {
          // Document icon placeholder
          img.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'></path><polyline points='14 2 14 8 20 8'></polyline><line x1='16' y1='13' x2='8' y2='13'></line><line x1='16' y1='17' x2='8' y2='17'></line><polyline points='10 9 9 9 8 9'></polyline></svg>";
          img.style.objectFit = 'contain';
          img.style.padding = '5px';
        }
      } catch (e) {
        console.error("Failed to load thumbnail:", e);
      }
      galleryPanel.appendChild(img);
    });
    
    setPreviewImage(0);
  } else {
    // Single Mode
    galleryPanel.classList.add('hidden');
    setPreviewImage(0);
  }
}

async function setPreviewImage(index) {
  if (index >= filesToProcess.length) return;
  const path = filesToProcess[index];
  currentProcessIndex = index;
  
  try {
    const ext = path.split('.').pop().toLowerCase();
    const isImage = ['png', 'jpg', 'jpeg', 'webp', 'bmp'].includes(ext);
    
    imgOriginal.onerror = null; // reset handler
    if (isImage) {
      const fileData = await window.__TAURI__.core.invoke('plugin:fs|read_file', { path });
      const blob = new Blob([new Uint8Array(fileData)]);
      const url = URL.createObjectURL(blob);
      imgOriginal.onerror = () => {
        alert("Image failed to load! URL: " + url);
        imgOriginal.onerror = null;
      };
      imgOriginal.src = url;
    } else {
      // Document icon placeholder
      imgOriginal.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ffffff' stroke-width='1' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'></path><polyline points='14 2 14 8 20 8'></polyline><line x1='16' y1='13' x2='8' y2='13'></line><line x1='16' y1='17' x2='8' y2='17'></line><polyline points='10 9 9 9 8 9'></polyline></svg>";
    }
  } catch (err) {
    alert("Failed to read file. Error: " + err + "\nPath: " + path);
  }
  
  if (translatedPaths[index]) {
      const outputPath = translatedPaths[index];
      if (window.__TAURI__?.core?.convertFileSrc) {
        imgTranslated.src = window.__TAURI__.core.convertFileSrc(outputPath) + '?t=' + Date.now();
      } else {
        // Fallback for web mode
        try {
            const fileData = await window.__TAURI__.core.invoke('plugin:fs|read_file', { path: outputPath });
            const blob = new Blob([new Uint8Array(fileData)]);
            imgTranslated.src = URL.createObjectURL(blob);
        } catch(e) {}
      }
      imgTranslated.style.opacity = '1';
  } else {
      imgTranslated.src = '';
      imgTranslated.style.opacity = '0.3';
  }
}

// IPC Simulation / Setup
let engineChild = null;

async function requestConfig() {
  try {
    const command = Command.sidecar('cypy_engine');
    
    command.stdout.on('data', line => {
      try {
        const msg = JSON.parse(line);
        if (msg.type === 'config') {
          // Fill UI with config from Python
          if(msg.data.LLM_PROVIDER) providerSelect.value = msg.data.LLM_PROVIDER;
          if(msg.data.MODEL) modelInput.value = msg.data.MODEL;
          if(msg.data.API_KEYS) {
            cachedApiKeys = msg.data.API_KEYS;
            updateApiKeyLabel(); // Update input value with the selected provider's key
          }
          
          if(msg.data.TWEAKS) {
            // ... (keep existing tweak logic)
            sfxMode.value = msg.data.TWEAKS.FILTER_SFX_MODE || 'seimbang';
            patchGepeng.checked = msg.data.TWEAKS.PAKAI_PATCH_UNTUK_BOX_GEPENG ?? true;
            padX.value = msg.data.TWEAKS.PAD_X_RATIO || 0.40;
            padY.value = msg.data.TWEAKS.PAD_Y_RATIO || 0.25;
            skala.value = msg.data.TWEAKS.SKALA_POTONGAN_MOSAIK || 2.0;
            minPad.value = msg.data.TWEAKS.MIN_PAD || 35;
            maskMargin.value = msg.data.TWEAKS.MASK_MARGIN_RATIO || 0.12;
            ['pad_x', 'pad_y', 'skala_potongan', 'min_pad', 'mask_margin'].forEach(id => {
              document.getElementById(id).dispatchEvent(new Event('input'));
            });
          }
        }
        
        // --- Translation Events ---
        if (msg.type === 'progress') {
          statusText.textContent = msg.message;
        }
        if (msg.type === 'result' || msg.status === 'success' || msg.status === 'done') {
          statusText.textContent = "Done!";
          (async () => {
            try {
              const outputPath = msg.output_image_path || msg.data?.output_image_path;
              if (outputPath) {
                translatedPaths[currentProcessIndex] = outputPath;
                if (window.__TAURI__?.core?.convertFileSrc) {
                  imgTranslated.src = window.__TAURI__.core.convertFileSrc(outputPath) + '?t=' + Date.now();
                } else {
                  // Fallback: read file bytes
                  const fileData = await window.__TAURI__.core.invoke('plugin:fs|read_file', { path: outputPath });
                  const blob = new Blob([new Uint8Array(fileData)]);
                  imgTranslated.src = URL.createObjectURL(blob);
                }
              }
            } catch (e) {
              console.error("Failed to load translated image:", e);
              imgTranslated.src = "";
            }
            imgTranslated.style.opacity = '1';
            loadingOverlay.classList.add('hidden');
            
            // Dispatch a custom event to notify translateBtn loop
            window.dispatchEvent(new CustomEvent('translation-complete'));
          })();
        }
        if (msg.type === 'error') {
          window.dispatchEvent(new CustomEvent('translation-error', { detail: msg.message }));
        }
      } catch(e) {}
    });

    const child = await command.spawn();
    await child.write(JSON.stringify({ action: "get_config" }) + '\n');
    engineChild = child;
  } catch (e) {
    const errorStr = (e instanceof Error) ? e.message : (typeof e === 'object' ? JSON.stringify(e) : String(e));
    console.warn("Sidecar failed to spawn:", e);
    alert("Warning: Background engine failed to start. Translations will not work.\nError: " + errorStr);
  }
}

saveConfigBtn.addEventListener('click', async () => {
  const config = {
    provider: providerSelect.value,
    model: modelInput.value,
    api_key: apiKeyInput.value,
    tweaks: {
      FILTER_SFX_MODE: sfxMode.value,
      PAKAI_PATCH_UNTUK_BOX_GEPENG: patchGepeng.checked,
      PAD_X_RATIO: parseFloat(padX.value),
      PAD_Y_RATIO: parseFloat(padY.value),
      SKALA_POTONGAN_MOSAIK: parseFloat(skala.value),
      MIN_PAD: parseInt(minPad.value),
      MASK_MARGIN_RATIO: parseFloat(maskMargin.value)
    }
  };
  
  if (engineChild) {
    await engineChild.write(JSON.stringify({ action: "save_config", payload: config }) + '\n');
  }
  
  settingsModal.classList.add('hidden');
});

// Translation Logic
translateBtn.addEventListener('click', async () => {
  if (filesToProcess.length === 0) return;
  
  translateBtn.disabled = true;
  
  for (let i = 0; i < filesToProcess.length; i++) {
    currentProcessIndex = i;
    
    // Update active thumb
    if (filesToProcess.length > 1) {
      document.querySelectorAll('.thumb').forEach(el => el.classList.remove('active'));
      document.getElementById(`thumb-${i}`).classList.add('active');
    }
    
    setPreviewImage(i);
    loadingOverlay.classList.remove('hidden');
    statusText.textContent = `Processing image ${i+1}/${filesToProcess.length}...`;
    translateBtn.textContent = `Translating (${i+1}/${filesToProcess.length})`;
    
    const absPath = filesToProcess[i];
    
    try {
      if (engineChild) {
        // Use real sidecar
        await new Promise((resolve, reject) => {
          const onComplete = () => { cleanup(); resolve(); };
          const onError = (e) => { cleanup(); reject(new Error(e.detail)); };
          
          function cleanup() {
            window.removeEventListener('translation-complete', onComplete);
            window.removeEventListener('translation-error', onError);
          }
          
          window.addEventListener('translation-complete', onComplete);
          window.addEventListener('translation-error', onError);
          
          engineChild.write(JSON.stringify({
            action: "translate",
            payload: {
              image_path: absPath,
              source_lang: "auto",
              target_lang: langSelect.value === 'custom' ? langCustom.value : langSelect.value
            }
          }) + '\n');
        });
      } else {
        setTimeout(() => loadingOverlay.classList.add('hidden'), 500);
      }
    } catch (e) {
      statusText.textContent = "Error: " + e.message;
      alert("Translation Failed: " + e.message);
      // Let it remain on screen so user can read it, then hide it after 3 secs
      setTimeout(() => loadingOverlay.classList.add('hidden'), 3000);
    }
    
    loadingOverlay.classList.add('hidden');
  }
  
  translateBtn.disabled = false;
  translateBtn.textContent = 'Translate';
});

window.addEventListener('DOMContentLoaded', () => {
  requestConfig();
});
