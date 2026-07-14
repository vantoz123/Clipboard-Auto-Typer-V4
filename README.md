# Clipboard Auto Typer v4.1

Clipboard Auto Typer is a Windows desktop application that reads copied text from the clipboard and inserts it into Microsoft Word or Google Docs/browser targets. This v4.1 build keeps the same app version but replaces action-key shortcut chords with a safer Command Mode popup so shortcut letters do not leak into Word, Google Docs, or browser fields.

## What is new in this v4.1 command-mode build

- Maintains the app version as **4.1.0**.
- Replaces the previous two-step letter shortcut chords with a small **Command Mode** popup.
- Press `Ctrl + Alt + Insert` once to open the popup, then click the action button you want.
- No second action letters such as `S`, `T`, `P`, `Q`, `H`, or `E` are captured globally, so they should not type into Google Docs, Word, or browser fields.
- Retains the v4.1 Browser Human Type Unicode fix for characters such as `ä`, `ö`, `ü`, `ñ`, symbols, and emojis.

## Main v4 features retained

- In-memory typing queue for copied clipboard items.
- Optional automatic typing of new queue items.
- Confirmation before typing.
- Edit-before-typing dialog.
- Editable preview window.
- Saved typing profiles:
  - Word - Exact
  - Word - Natural Type
  - Google Docs - Exact Paste
  - Google Docs - Natural Type
- Improved Google Docs/browser support, including SunBrowser and other Chromium-based browsers.
- Test Typing button.
- Diagnostics window and `run_diagnostics.bat`.
- Export Log button.
- Dark mode toggle.
- Ignore duplicate clipboard text.
- Countdown before typing starts.
- Emergency stop clears pending queue items.
- Portable EXE build helper.

## Supported targets

### Microsoft Word

Recommended mode:

```text
Destination: Microsoft Word
Typing method: Safe Insert (Word exact)
```

This uses Microsoft Word COM automation and provides the best preservation of Unicode, line breaks, symbols, and spacing in Word.

### Google Docs / Browser

Recommended mode for maximum reliability:

```text
Destination: Google Docs / Browser
Typing method: Browser Paste (Google Docs exact)
```

Recommended mode for visible natural typing with Unicode support:

```text
Destination: Google Docs / Browser
Typing method: Browser Human Type (hybrid Unicode)
```

Browser Human Type now automatically handles accented letters and emojis by using exact fallback paste only for those characters. Normal characters are still typed with natural randomized delays.

## System requirements

- Windows 10 or Windows 11.
- Python 3.9 or later.
- Microsoft Word for Word modes.
- A supported browser for Google Docs/browser modes.
- Google Docs requires an internet connection unless your Google Docs environment is already available offline.

## Installation

1. Extract the ZIP file.
2. Open the project folder.
3. Double-click:

```text
install_dependencies.bat
```

This creates a virtual environment and installs the required Python packages.

## Run the app

Double-click:

```text
run_app.bat
```

Or run manually from PowerShell inside the folder containing `main.py`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Build the executable

Double-click:

```text
build_exe.bat
```

The EXE will be created in:

```text
dist\Clipboard Auto Typer v4.1.exe
```

To prepare a portable folder, double-click:

```text
build_portable_folder.bat
```

## Command Mode control

This build uses one global shortcut only:

```text
Ctrl + Alt + Insert
```

Pressing it opens a small **Clipboard Auto Typer - Command Mode** popup. Then click one of these buttons:

| Button | Action |
|---|---|
| Start Monitoring | Starts clipboard monitoring |
| Stop + Clear Queue | Stops typing/monitoring and clears pending queue items |
| Pause / Resume | Pauses or resumes typing |
| Type Selected Queue Item | Types the currently selected queue item |
| Type Current Clipboard | Types the current clipboard text |
| Show / Hide Main Window | Shows or hides the main app window |
| Emergency Stop | Immediately stops typing and clears pending actions |
| Close | Closes only the Command Mode popup |

Why this is safer: the app no longer waits for a second global letter key like `S`, `T`, `P`, `Q`, or `H`. Those letters are no longer sent as command shortcuts, so they should not leak into Google Docs, Microsoft Word, SunBrowser, Chrome, Edge, or other browser text fields.

`Esc` still performs Emergency Stop when the main app window is focused. Inside the Command Mode popup, `Esc` closes the popup.

## Queue workflow

1. Start monitoring.
2. Copy text from any source.
3. The text appears in the Typing Queue and preview window.
4. Select a queue item.
5. Optionally edit it.
6. Click **Type Selected**.
7. Click inside Word or Google Docs before the countdown ends.

## Browser Human Type Unicode behavior

In v4.1, Browser Human Type will not stop when it reaches text like:

```text
Special characters: ä ö ü ñ
Emoji test: 😊 🚀 ✅
```

Instead, it will:

1. Type ordinary characters normally.
2. Temporarily copy only the unsupported Unicode/accent/emoji segment.
3. Press Ctrl+V to insert that segment into Google Docs exactly.
4. Continue typing the rest normally.
5. Restore the previous clipboard content after typing when enabled.

For very long text with many emojis or complex Unicode, Browser Paste is still the fastest and most reliable Google Docs method.

## Privacy and offline behavior

The application itself does not send data online, does not collect user data, does not require an account, and does not store clipboard text on disk. Settings and profiles store only non-sensitive app preferences.

Important notes:

- Installing dependencies may require internet access.
- Microsoft Word mode can run offline after installation.
- Google Docs/browser mode depends on the browser/web app you are typing into. Google Docs may sync typed content through Google as usual.
- Browser Paste and Browser Human Type Unicode fallback may temporarily place the text being inserted on the clipboard, then restore the previous clipboard when the restore option is enabled.

## Troubleshooting

### PowerShell blocks activation

Run this in the current PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again:

```powershell
.venv\Scripts\Activate.ps1
```

### main.py is not recognized

Run it with Python:

```powershell
python main.py
```

Do not type only `main.py`.

### PyInstaller says scriptname is required

Run PyInstaller with the script name:

```powershell
python -m PyInstaller --onefile --windowed --name "Clipboard Auto Typer v4.1" main.py
```

### Browser not detected

Use Google Docs / Browser mode and make sure your browser is active. v4.1 includes common browsers such as Chrome, Edge, Firefox, Brave, Opera, Vivaldi, SunBrowser, and AdsPower-related browser processes.

### Accented letters or emojis caused a warning in older versions

Use v4.1 and select:

```text
Typing method: Browser Human Type (hybrid Unicode)
```

or:

```text
Typing method: Browser Paste (Google Docs exact)
```

## Project structure

```text
Clipboard_Auto_Typer_v4_1_command_mode/
├── main.py
├── clipboard_manager.py
├── typer_engine.py
├── target_detector.py
├── word_detector.py
├── gui.py
├── config.py
├── settings_manager.py
├── profile_manager.py
├── diagnostics.py
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── USER_MANUAL.pdf
├── install_dependencies.bat
├── run_app.bat
├── run_diagnostics.bat
├── build_exe.bat
├── build_portable_folder.bat
├── screenshots/
└── logs/
```

### Command Mode popup close fix

In this build, the Command Mode popup's **Close / Hide Popup** button hides the popup instead of destroying it. Press **Ctrl + Alt + Insert** again to reopen it. This prevents a stale Tkinter popup reference from blocking the popup after it has been closed.
