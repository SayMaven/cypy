"""
cypy/gui/theme.py
✦ Centralized GUI Theme Constants ✦

Single source of truth for all color and font constants used across
the GUI. Previously duplicated in window.py, widgets.py, and info.py.
"""

# ==========================================
# ✦ COLOR PALETTE ✦
# ==========================================
COLOR_BG = "#121212"              # Outer window background
COLOR_CARD = "#222222"            # Elevating card containers (high contrast medium dark)
COLOR_WIDGET = "#161616"          # Recessed inputs / Dropdowns / Log Textbox
COLOR_BORDER = "#2e2e2e"          # Subtle border lines
COLOR_PINK = "#db2777"            # Vibrant Magenta Pink Accent
COLOR_WHITE = "#ffffff"           # Titles and major texts
COLOR_GRAY = "#aaaaaa"            # Subdued labels
COLOR_DARK_BTN = "#2e2e2e"        # Secondary buttons (FILE, FOLDER)
COLOR_DARK_BTN_HOVER = "#3e3e3e"  # Secondary button hover
COLOR_GREEN = "#00ff00"           # Status indicator: Ready
COLOR_ORANGE = "#e69933"          # Status indicator: Processing
COLOR_RED = "#ff3333"             # Status indicator: Error

# ==========================================
# ✦ FONT PRESETS ✦
# ==========================================
FONT_TERMINAL_SM = ("Terminal", 9, "bold")
FONT_TERMINAL_MD = ("Terminal", 10)
FONT_TERMINAL_MD_BOLD = ("Terminal", 10, "bold")
FONT_TERMINAL_LG = ("Terminal", 13)
FONT_CONSOLAS_SM = ("Consolas", 10)
