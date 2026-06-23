# cypy

cypy is a powerful, minimal, and cross-platform command-line (CLI) manga translation package built with Python. Using YOLOv8 for precise speech bubble detection and the Google Gemini API for context-aware translation, cypy automates the translation of Japanese / Chinese / Other manga panels to Indonesian while ensuring clean text erasure and beautiful typography placement.

## Comparison

| Before (Original Japanese / Chinese / Other) | After (Translated Indonesian) |
| :---: | :---: |
| ![Original Japanese Manga Page](assets/before.jpg) | ![Translated Indonesian Manga Page](assets/after.png) |

## Features

- **YOLOv8 Speech Bubble Detection:** Automatically and accurately isolates speech bubbles on any manga page.
- **Context-Aware Gemini Translation:** Groups detected bubbles, creates a temporary mosaic preview for context, and sends them to Gemini to generate high-quality, natural Indonesian translations.
- **Clean Image Erasure (Masking):** Uses dynamic ellipse masking and Gaussian blur to cover original Japanese text cleanly without leaving harsh edges.
- **Auto-Fit Typography:** Smart word wrapping, hyphen splitting, and dynamic font scaling ensure the translated text fits speech bubbles perfectly.
- **PDF Translation Pipeline:** Seamlessly extract pages from a PDF, translate each page individually, and compile them back into a single translated PDF.
- **Professional Developer Logging:** Minimalistic console logging that only prints essential progress updates, keeping developer and user terminals clean.
- **Cross-Platform Support:** Tested and fully compatible with Windows, Linux, and macOS.

## Prerequisites

- **Python 3.8+**
- **Assets (YOLO Model & Font):** Ensure that the following assets are placed in the `assets/` directory:
  - `eyecyre.pt` (YOLO model weights)
  - `Komika Axis.ttf` (Manga-styled font)
- **Google Gemini API Key:** You will need an API key to access the Gemini translation gate.

## Installation

cypy is structured as a standard Python package. It is highly recommended to install it inside a Python virtual environment to keep dependencies isolated and manage your environment cleanly.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/indravoyager/cypy.git
   cd cypy
   ```

2. **Create a Python virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - **Windows (Command Prompt):**
     ```cmd
     venv\Scripts\activate.bat
     ```
   - **Windows (PowerShell):**
     ```powershell
     venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS:**
     ```bash
     source venv/bin/activate
     ```

4. **Install the package in editable mode:**
   ```bash
   pip install -e .
   ```
   *(This automatically installs core dependencies like `opencv-python`, `PyMuPDF` (fitz), `numpy`, `Pillow`, `ultralytics`, `google-genai`, and `python-dotenv` inside the active environment).*

## Configuration

To configure the API key, copy the template `.env.example` file to `.env` in the root directory:

- **Windows (CMD / PowerShell):**
  ```cmd
  copy .env.example .env
  ```
- **Linux / macOS:**
  ```bash
  cp .env.example .env
  ```

Then, open the newly created `.env` file and replace the placeholder with your Google Gemini API Key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Additional parameters like margins, font scaling, and filter sensitivities can be configured inside `cypy/core/config.py`.

## Usage

Since cypy is installed as a package, you can run it from **any directory** in your terminal:

```bash
cypy
```

Alternatively, you can run it directly from the project root:

```bash
python -m cypy
```

### Operation Steps:
1. When launched, the application will initialize YOLO and prompt you to input a file.
2. **Drag-and-drop** your manga image (`.png`, `.jpg`, `.jpeg`, `.webp`) or PDF file (`.pdf`) directly into the terminal window.
3. Press **Enter** to start translating.
4. The translated image/PDF will be generated in the same directory as the source file (suffixed with `_translated`).
5. Type `stop` to exit the translator loop.

## Project Structure

```text
CYPY - Manga Translator/
├── assets/              # Model weights (eyecyre.pt) and font files (Komika Axis.ttf)
├── cypy/                # Core Python package
│   ├── app.py           # Application entrypoint & loop
│   ├── __main__.py      # Package executor
│   └── core/            # Core engine modules
│       ├── config.py    # Path management and processing parameters
│       ├── translator.py# YOLO detection, mosaic creation, and translation orchestration
│       └── utils.py     # Image filtering, text fitting, and masking helpers
├── cypy_cache/          # Temporary directory for mosaic drafts and page caching (Git ignored)
├── pyproject.toml       # Modern Python packaging configuration
└── README.md
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
