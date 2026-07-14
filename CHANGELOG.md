# Changelog

## v4.1.0 command-mode build

### Shortcut control update

- Maintains the application version as v4.1.0.
- Replaces action-letter shortcut chords with a single Command Mode hotkey: `Ctrl + Alt + Insert`.
- Pressing `Ctrl + Alt + Insert` opens a small app-owned popup with clickable controls.
- Removed global action letters such as `S`, `X`, `P`, `Q`, `T`, `H`, and `E`, preventing those letters from leaking into Google Docs, Microsoft Word, SunBrowser, Chrome, Edge, or other browser inputs.
- Added a **Command Mode** button in the main GUI.
- Updated GUI shortcut text, README, and user manual.

## v4.1.0 original shortcut hotfix - superseded by command-mode build

### Shortcut hotfix

- Replaced direct global shortcuts with two-step shortcut chords while keeping the app version as v4.1.0.
- New leader key: `Ctrl + Alt + Insert`.
- New actions: `S` start, `X` stop, `P` pause/resume, `Q` type selected, `T` type clipboard, `H` show/hide, and `E` emergency stop.
- Removed direct Ctrl+Alt+function-key shortcuts to reduce conflicts in Google Docs, Microsoft Word, and Chromium-based browsers.
- Added local shortcut chord support when the app window is focused.

### Fixed

- Fixed Browser Human Type stopping on accented characters such as `ä`, `ö`, `ü`, and `ñ`.
- Fixed Browser Human Type stopping on emojis or other Unicode characters supported by Google Docs.

### Added

- Added hybrid Unicode fallback for Google Docs/browser human typing.
- Normal keyboard characters are still typed with randomized human-like delay.
- Unicode/accent/emoji segments are inserted exactly through short temporary clipboard paste operations.
- Clipboard restoration is performed after Unicode fallback when the restore option is enabled.
- Added support for common emoji format controls, including variation selectors and zero-width joiner sequences.

### Updated

- Updated GUI guidance for Browser Human Type.
- Updated README and user manual.
- Updated app version to 4.1.0.
- Updated PyInstaller build names to v4.1.

## v4.0.0

### Added

- Typing queue.
- Confirm-before-typing workflow.
- Edit-before-typing workflow.
- Typing profiles.
- Better Google Docs/browser support.
- SunBrowser and AdsPower-related browser process detection.
- Test Typing button.
- Diagnostics window.
- Export Log button.
- Dark mode toggle.
- Ignore duplicate clipboard option.
- Countdown before typing.
- Stronger emergency stop behavior.
- Portable EXE folder helper.

## v4.1.0 - Command Mode popup reopen fix

- Kept the application version at `4.1.0`.
- Fixed Command Mode so the popup can be reopened after pressing Close.
- Changed the popup button label to **Close / Hide Popup**.
- Close now withdraws the popup instead of destroying it.
- Added cleanup protection if Windows/Tk actually destroys the popup.
- Avoided making the popup transient when the main window is hidden to tray.
