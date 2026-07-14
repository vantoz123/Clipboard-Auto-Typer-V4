"""Application configuration for Clipboard Auto Typer v4.1."""

from __future__ import annotations

APP_NAME = "Clipboard Auto Typer"
APP_VERSION = "4.1.0"
APP_ID = "ClipboardAutoTyperV4_1"

CLIPBOARD_POLL_INTERVAL = 0.50
DEFAULT_DELAY_SECONDS = 3.0
COUNTDOWN_UPDATE_SECONDS = 1.0

SPEED_PRESETS = {
    "Slow": 5,
    "Normal": 25,
    "Fast": 60,
}
DEFAULT_SPEED_MODE = "Normal"
MIN_CPS = 1
MAX_CPS = 200

TARGET_MODE_AUTO = "Auto Detect"
TARGET_MODE_WORD = "Microsoft Word"
TARGET_MODE_GOOGLE_DOCS = "Google Docs / Browser"
TARGET_MODES = (TARGET_MODE_AUTO, TARGET_MODE_WORD, TARGET_MODE_GOOGLE_DOCS)
DEFAULT_TARGET_MODE = TARGET_MODE_AUTO

INSERTION_MODE_SAFE_WORD = "Safe Insert (Word exact)"
INSERTION_MODE_WORD_HUMAN = "Word Human Type"
INSERTION_MODE_BROWSER_PASTE = "Browser Paste (Google Docs exact)"
INSERTION_MODE_BROWSER_HUMAN = "Browser Human Type (hybrid Unicode)"
INSERTION_MODES = (
    INSERTION_MODE_SAFE_WORD,
    INSERTION_MODE_WORD_HUMAN,
    INSERTION_MODE_BROWSER_PASTE,
    INSERTION_MODE_BROWSER_HUMAN,
)
DEFAULT_INSERTION_MODE = INSERTION_MODE_SAFE_WORD

DEFAULT_RANDOM_DELAY_ENABLED = True
DEFAULT_RANDOM_DELAY_MIN_SECONDS = 0.01
DEFAULT_RANDOM_DELAY_MAX_SECONDS = 0.05
MIN_RANDOM_DELAY_SECONDS = 0.00
MAX_RANDOM_DELAY_SECONDS = 2.00

DEFAULT_MINIMIZE_TO_TRAY = True
DEFAULT_CONFIRM_BEFORE_TYPING = True
DEFAULT_EDIT_BEFORE_TYPING = False
DEFAULT_IGNORE_DUPLICATES = True
DEFAULT_RESTORE_CLIPBOARD_AFTER_PASTE = True
DEFAULT_DARK_MODE = False
DEFAULT_QUEUE_LIMIT = 25
DEFAULT_AUTO_TYPE_NEW_ITEMS = False
MAX_QUEUE_ITEMS = 100

# Global command mode shortcut. Version 4.1 keeps only one global shortcut:
# Ctrl+Alt+Insert opens a small command popup. Actions are then selected from
# buttons inside the popup, not by sending a second letter key to Word, Google
# Docs, or the browser. This avoids conflicts such as Ctrl+Shift+T, Ctrl+S,
# Ctrl+P, Ctrl+F, direct function-key shortcuts, and chord letters leaking into
# the active document.
COMMAND_MODE_HOTKEY = "ctrl+alt+insert"
COMMAND_MODE_HOTKEY_LABEL = "Ctrl + Alt + Insert"
LOCAL_COMMAND_MODE_HOTKEY = "<Control-Alt-Insert>"
LOCAL_SHORTCUTS = {
    "emergency_stop": "<Escape>",
}

MAX_PREVIEW_CHARS = 6000
MAX_LOG_LINES = 800
TARGET_ACTIVE_CHECK_INTERVAL_CHARS = 10
SETTINGS_FILENAME = "settings_v4_1.json"
PROFILES_FILENAME = "profiles_v4_1.json"
LOG_EXPORT_PREFIX = "clipboard_auto_typer_log"

SUPPORTED_BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "opera_gx.exe",
    "vivaldi.exe",
    "browser.exe",
    "sunbrowser.exe",
    "adspower.exe",
    "chromium.exe",
    "yandex.exe",
    "dragon.exe",
    "waterfox.exe",
}

GOOGLE_DOCS_TITLE_HINTS = (
    "google docs",
    "docs.google.com",
    " - docs",
    "docs - google",
)

TEST_TEXT = "Clipboard Auto Typer test: 123 @#$ ä ö ü ñ 😊\nSecond line preserved."
