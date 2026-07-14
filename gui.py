"""Tkinter GUI for Clipboard Auto Typer v4.1."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, scrolledtext, ttk
from typing import Callable, Optional

import config
from clipboard_manager import ClipboardEvent, ClipboardMonitor, text_fingerprint
from diagnostics import format_diagnostics
from profile_manager import DEFAULT_PROFILES, ProfileManager
from settings_manager import SettingsManager, app_data_dir
from target_detector import TargetDetector
from typer_engine import TyperEngine, TypingOptions

try:
    import keyboard  # type: ignore
except Exception:
    keyboard = None

try:
    import pyperclip  # type: ignore
except Exception:
    pyperclip = None

try:
    import pystray  # type: ignore
    from PIL import Image, ImageDraw  # type: ignore
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


@dataclass
class QueueItem:
    item_id: int
    text: str
    fingerprint: str
    created_at: datetime
    source: str = "Clipboard"

    @property
    def display_label(self) -> str:
        one_line = self.text.replace("\r", " ").replace("\n", " ").replace("\t", "    ").strip()
        if len(one_line) > 72:
            one_line = one_line[:69] + "..."
        return f"{self.created_at.strftime('%H:%M:%S')} | {len(self.text)} chars | {self.source} | {one_line or '[blank]'}"


class ClipboardAutoTyperApp:
    """Main GUI application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{config.APP_NAME} {config.APP_VERSION}")
        self.root.minsize(1080, 820)

        self.ui_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.queue_items: list[QueueItem] = []
        self.next_queue_id = 1
        self.current_clipboard_text = ""
        self.last_typed_fingerprint: Optional[str] = None
        self.hotkey_registered_names: list[object] = []
        self.command_popup: Optional[tk.Toplevel] = None
        self.tray_icon = None
        self.tray_thread: Optional[threading.Thread] = None
        self.exiting = False
        self._minimize_event_in_progress = False

        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load()
        self.profile_manager = ProfileManager()
        self.profiles = self.profile_manager.load()

        self.monitor = ClipboardMonitor(
            on_text=self._on_clipboard_text,
            on_error=lambda message: self._enqueue("log", f"ERROR: {message}"),
            on_status=lambda message: self._enqueue("log", message),
        )
        self.typer = TyperEngine(
            on_log=lambda message: self._enqueue("log", message),
            on_done=lambda success, message: self._enqueue("done", (success, message)),
            on_progress=lambda current, total: self._enqueue("progress", (current, total)),
            on_countdown=lambda seconds: self._enqueue("countdown", seconds),
        )

        self._init_variables()
        self._configure_style()
        self._build_ui()
        self._refresh_profile_combo()
        self._apply_dark_mode()
        self._register_shortcuts()
        self._setup_tray_icon()
        self._schedule_queue_processing()
        self._schedule_target_status_update()

        self.root.protocol("WM_DELETE_WINDOW", self.confirm_exit)
        self.root.bind("<Unmap>", self._on_window_unmap)
        self._log(f"Application started: {config.APP_NAME} v{config.APP_VERSION}.")
        self._log("Privacy: clipboard text is not stored to disk, not uploaded, and not sent to any server by this app.")
        self._log("v4.1 queue mode: copied text is added to the in-memory queue. Use Type Selected or enable Auto type new items.")

    def _init_variables(self) -> None:
        self.status_var = tk.StringVar(value="Stopped")
        self.target_status_var = tk.StringVar(value="Checking target...")
        self.progress_var = tk.StringVar(value="Progress: idle")
        self.countdown_var = tk.StringVar(value="Countdown: idle")
        self.queue_status_var = tk.StringVar(value="Queue: empty")
        self.shortcut_status_var = tk.StringVar(value="Command Mode: not registered")
        self.tray_status_var = tk.StringVar(value="Tray: not started")

        self.profile_var = tk.StringVar(value=str(self.settings.get("active_profile", "Word - Exact")))
        self.speed_mode_var = tk.StringVar(value=str(self.settings.get("speed_mode", config.DEFAULT_SPEED_MODE)))
        self.custom_cps_var = tk.StringVar(value=str(self.settings.get("custom_cps", config.SPEED_PRESETS[config.DEFAULT_SPEED_MODE])))
        self.delay_var = tk.StringVar(value=str(self.settings.get("delay_seconds", config.DEFAULT_DELAY_SECONDS)))
        self.target_mode_var = tk.StringVar(value=str(self.settings.get("target_mode", config.DEFAULT_TARGET_MODE)))
        self.insertion_mode_var = tk.StringVar(value=str(self.settings.get("insertion_mode", config.DEFAULT_INSERTION_MODE)))
        self.random_delay_enabled_var = tk.BooleanVar(value=bool(self.settings.get("random_delay_enabled", True)))
        self.random_delay_min_var = tk.StringVar(value=str(self.settings.get("random_delay_min_seconds", config.DEFAULT_RANDOM_DELAY_MIN_SECONDS)))
        self.random_delay_max_var = tk.StringVar(value=str(self.settings.get("random_delay_max_seconds", config.DEFAULT_RANDOM_DELAY_MAX_SECONDS)))
        self.ignore_current_var = tk.BooleanVar(value=bool(self.settings.get("ignore_current_clipboard_on_start", True)))
        self.minimize_to_tray_var = tk.BooleanVar(value=bool(self.settings.get("minimize_to_tray", config.DEFAULT_MINIMIZE_TO_TRAY)))
        self.confirm_before_typing_var = tk.BooleanVar(value=bool(self.settings.get("confirm_before_typing", config.DEFAULT_CONFIRM_BEFORE_TYPING)))
        self.edit_before_typing_var = tk.BooleanVar(value=bool(self.settings.get("edit_before_typing", config.DEFAULT_EDIT_BEFORE_TYPING)))
        self.ignore_duplicates_var = tk.BooleanVar(value=bool(self.settings.get("ignore_duplicates", config.DEFAULT_IGNORE_DUPLICATES)))
        self.restore_clipboard_var = tk.BooleanVar(value=bool(self.settings.get("restore_clipboard_after_paste", config.DEFAULT_RESTORE_CLIPBOARD_AFTER_PASTE)))
        self.dark_mode_var = tk.BooleanVar(value=bool(self.settings.get("dark_mode", config.DEFAULT_DARK_MODE)))
        self.queue_limit_var = tk.StringVar(value=str(self.settings.get("queue_limit", config.DEFAULT_QUEUE_LIMIT)))
        self.auto_type_new_items_var = tk.BooleanVar(value=bool(self.settings.get("auto_type_new_items", config.DEFAULT_AUTO_TYPE_NEW_ITEMS)))

    def _configure_style(self) -> None:
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(outer, text=f"{config.APP_NAME} v{config.APP_VERSION}", font=("Segoe UI", 18, "bold"))
        title_label.pack(anchor=tk.W)
        subtitle = ttk.Label(
            outer,
            text="Insert copied text into Microsoft Word or Google Docs with queue control, profiles, confirmation, edit-before-typing, and safe emergency stop.",
            wraplength=1020,
        )
        subtitle.pack(anchor=tk.W, pady=(0, 10))

        self._build_status_section(outer)
        self._build_controls_section(outer)
        self._build_profile_and_options_section(outer)
        self._build_queue_and_preview_section(outer)
        self._build_log_section(outer)

    def _build_status_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Status", padding=10)
        frame.pack(fill=tk.X)
        labels = [
            ("Monitoring:", self.status_var),
            ("Target:", self.target_status_var),
            ("Progress:", self.progress_var),
            ("Countdown:", self.countdown_var),
            ("Queue:", self.queue_status_var),
        ]
        for col, (label, var) in enumerate(labels):
            ttk.Label(frame, text=label).grid(row=0, column=col * 2, sticky=tk.W, padx=(0, 5))
            ttk.Label(frame, textvariable=var, font=("Segoe UI", 9, "bold") if col == 0 else None).grid(row=0, column=col * 2 + 1, sticky=tk.W, padx=(0, 12))
        ttk.Label(frame, textvariable=self.shortcut_status_var).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(6, 0))
        ttk.Label(frame, textvariable=self.tray_status_var).grid(row=1, column=4, columnspan=3, sticky=tk.W, pady=(6, 0))
        frame.columnconfigure(9, weight=1)

    def _build_controls_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Main Controls", padding=10)
        frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(frame, text="Start Monitoring", command=self.start_monitoring).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Stop + Clear Queue", command=self.emergency_stop).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Pause / Resume", command=self.toggle_pause_typing).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Type Selected", command=self.type_selected_queue_item).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Type Current Clipboard", command=self.type_current_clipboard).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Test Typing", command=self.add_test_text).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Diagnostics", command=self.show_diagnostics).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Command Mode", command=self.show_command_mode_popup).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Hide to Tray", command=self.hide_to_tray).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(frame, text="Exit", command=self.confirm_exit).pack(side=tk.RIGHT)

    def _build_profile_and_options_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Profiles, Destination, Speed, and Safety Options", padding=10)
        frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(frame, text="Profile:").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.profile_combo = ttk.Combobox(frame, textvariable=self.profile_var, values=[], state="readonly", width=28)
        self.profile_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 6))
        ttk.Button(frame, text="Apply", command=self.apply_selected_profile).grid(row=0, column=2, sticky=tk.W, padx=(0, 6))
        ttk.Button(frame, text="Save Current as Profile", command=self.save_current_profile).grid(row=0, column=3, sticky=tk.W, padx=(0, 6))
        ttk.Button(frame, text="Delete Profile", command=self.delete_selected_profile).grid(row=0, column=4, sticky=tk.W)

        ttk.Label(frame, text="Destination:").grid(row=1, column=0, sticky=tk.W, padx=(0, 4), pady=(10, 0))
        target_combo = ttk.Combobox(frame, textvariable=self.target_mode_var, values=config.TARGET_MODES, state="readonly", width=24)
        target_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 12), pady=(10, 0))
        target_combo.bind("<<ComboboxSelected>>", lambda _event: self._save_settings_safely())

        ttk.Label(frame, text="Typing method:").grid(row=1, column=2, sticky=tk.W, padx=(0, 4), pady=(10, 0))
        insertion_combo = ttk.Combobox(frame, textvariable=self.insertion_mode_var, values=config.INSERTION_MODES, state="readonly", width=31)
        insertion_combo.grid(row=1, column=3, columnspan=2, sticky=tk.W, pady=(10, 0))
        insertion_combo.bind("<<ComboboxSelected>>", lambda _event: self._save_settings_safely())

        ttk.Label(frame, text="Speed:").grid(row=2, column=0, sticky=tk.W, padx=(0, 4), pady=(10, 0))
        speed_combo = ttk.Combobox(frame, textvariable=self.speed_mode_var, values=(*config.SPEED_PRESETS.keys(), "Custom"), state="readonly", width=10)
        speed_combo.grid(row=2, column=1, sticky=tk.W, pady=(10, 0))
        speed_combo.bind("<<ComboboxSelected>>", lambda _event: self._save_settings_safely())

        ttk.Label(frame, text="Custom CPS:").grid(row=2, column=2, sticky=tk.W, padx=(0, 4), pady=(10, 0))
        cps_entry = ttk.Entry(frame, textvariable=self.custom_cps_var, width=8)
        cps_entry.grid(row=2, column=3, sticky=tk.W, pady=(10, 0))
        cps_entry.bind("<FocusOut>", lambda _event: self._save_settings_safely())

        ttk.Label(frame, text="Start delay:").grid(row=2, column=4, sticky=tk.E, padx=(8, 4), pady=(10, 0))
        delay_entry = ttk.Entry(frame, textvariable=self.delay_var, width=8)
        delay_entry.grid(row=2, column=5, sticky=tk.W, pady=(10, 0))
        delay_entry.bind("<FocusOut>", lambda _event: self._save_settings_safely())
        ttk.Label(frame, text="sec").grid(row=2, column=6, sticky=tk.W, pady=(10, 0))

        ttk.Checkbutton(frame, text="Natural randomized key delay", variable=self.random_delay_enabled_var, command=self._save_settings_safely).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        ttk.Label(frame, text="Min:").grid(row=3, column=2, sticky=tk.E, padx=(0, 4), pady=(10, 0))
        min_entry = ttk.Entry(frame, textvariable=self.random_delay_min_var, width=8)
        min_entry.grid(row=3, column=3, sticky=tk.W, pady=(10, 0))
        min_entry.bind("<FocusOut>", lambda _event: self._save_settings_safely())
        ttk.Label(frame, text="Max:").grid(row=3, column=4, sticky=tk.E, padx=(0, 4), pady=(10, 0))
        max_entry = ttk.Entry(frame, textvariable=self.random_delay_max_var, width=8)
        max_entry.grid(row=3, column=5, sticky=tk.W, pady=(10, 0))
        max_entry.bind("<FocusOut>", lambda _event: self._save_settings_safely())

        options = ttk.Frame(frame)
        options.grid(row=4, column=0, columnspan=7, sticky=tk.W, pady=(10, 0))
        option_specs = [
            ("Auto type new queue items", self.auto_type_new_items_var),
            ("Confirm before typing", self.confirm_before_typing_var),
            ("Edit before typing", self.edit_before_typing_var),
            ("Ignore duplicates", self.ignore_duplicates_var),
            ("Restore clipboard after Browser Paste", self.restore_clipboard_var),
            ("Minimize to tray", self.minimize_to_tray_var),
            ("Dark mode", self.dark_mode_var),
            ("Ignore current clipboard on start", self.ignore_current_var),
        ]
        for index, (text, var) in enumerate(option_specs):
            cb = ttk.Checkbutton(options, text=text, variable=var, command=self._on_option_changed)
            cb.grid(row=index // 4, column=index % 4, sticky=tk.W, padx=(0, 18), pady=(0, 4))

        ttk.Label(frame, text="Queue limit:").grid(row=5, column=0, sticky=tk.W, padx=(0, 4), pady=(8, 0))
        queue_limit_entry = ttk.Entry(frame, textvariable=self.queue_limit_var, width=8)
        queue_limit_entry.grid(row=5, column=1, sticky=tk.W, pady=(8, 0))
        queue_limit_entry.bind("<FocusOut>", lambda _event: self._save_settings_safely())

        note = ttk.Label(
            frame,
            text="Browser Human Type now uses hybrid Unicode fallback: common characters are typed naturally, while accents/emojis are inserted exactly with a temporary clipboard paste. Browser Paste remains fastest for long exact Google Docs insertion.",
            wraplength=1000,
        )
        note.grid(row=6, column=0, columnspan=7, sticky=tk.W, pady=(8, 0))
        frame.columnconfigure(7, weight=1)

    def _build_queue_and_preview_section(self, parent: ttk.Frame) -> None:
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        queue_frame = ttk.LabelFrame(paned, text="Typing Queue", padding=8)
        paned.add(queue_frame, weight=1)
        self.queue_listbox = tk.Listbox(queue_frame, height=12, exportselection=False)
        self.queue_listbox.pack(fill=tk.BOTH, expand=True)
        self.queue_listbox.bind("<<ListboxSelect>>", lambda _event: self._preview_selected_queue_item())
        queue_buttons = ttk.Frame(queue_frame)
        queue_buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(queue_buttons, text="Add Clipboard", command=self.add_current_clipboard_to_queue).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(queue_buttons, text="Edit", command=self.edit_selected_queue_item).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(queue_buttons, text="Remove", command=self.remove_selected_queue_item).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(queue_buttons, text="Clear", command=self.clear_queue).pack(side=tk.LEFT, padx=(0, 4))

        preview_frame = ttk.LabelFrame(paned, text="Preview / Edit Before Typing", padding=8)
        paned.add(preview_frame, weight=2)
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=12, wrap=tk.WORD, font=("Consolas", 10))
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        preview_buttons = ttk.Frame(preview_frame)
        preview_buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(preview_buttons, text="Update Selected from Preview", command=self.update_selected_from_preview).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(preview_buttons, text="Load Current Clipboard", command=self.load_current_clipboard_to_preview).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(preview_buttons, text="Type Preview Text", command=self.type_preview_text).pack(side=tk.LEFT, padx=(0, 4))

    def _build_log_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Activity Log", padding=8)
        frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Export Log", command=self.export_log).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(buttons, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=(0, 4))
        shortcut_text = (
            f"Command Mode: press {config.COMMAND_MODE_HOTKEY_LABEL} to open the control popup, "
            "then click Start, Stop, Pause, Type, Hide/Show, or Emergency Stop. "
            "Esc still performs Emergency Stop when the main app window is focused."
        )
        ttk.Label(buttons, text=shortcut_text, wraplength=850).pack(side=tk.LEFT, padx=(12, 0))

    def _refresh_profile_combo(self) -> None:
        names = sorted(self.profiles.keys())
        self.profile_combo.configure(values=names)
        if self.profile_var.get() not in names and names:
            self.profile_var.set(names[0])

    def apply_selected_profile(self) -> None:
        name = self.profile_var.get()
        profile = self.profiles.get(name)
        if not profile:
            self._log(f"WARNING: Profile not found: {name}")
            return
        self.target_mode_var.set(str(profile.get("target_mode", config.DEFAULT_TARGET_MODE)))
        self.insertion_mode_var.set(str(profile.get("insertion_mode", config.DEFAULT_INSERTION_MODE)))
        self.speed_mode_var.set(str(profile.get("speed_mode", config.DEFAULT_SPEED_MODE)))
        self.custom_cps_var.set(str(profile.get("custom_cps", config.SPEED_PRESETS[config.DEFAULT_SPEED_MODE])))
        self.delay_var.set(str(profile.get("delay_seconds", config.DEFAULT_DELAY_SECONDS)))
        self.random_delay_enabled_var.set(bool(profile.get("random_delay_enabled", config.DEFAULT_RANDOM_DELAY_ENABLED)))
        self.random_delay_min_var.set(str(profile.get("random_delay_min_seconds", config.DEFAULT_RANDOM_DELAY_MIN_SECONDS)))
        self.random_delay_max_var.set(str(profile.get("random_delay_max_seconds", config.DEFAULT_RANDOM_DELAY_MAX_SECONDS)))
        self._save_settings_safely()
        self._log(f"Applied profile: {name}")

    def save_current_profile(self) -> None:
        name = simpledialog.askstring("Save Profile", "Enter a profile name:", parent=self.root)
        if not name:
            return
        self.profiles[name.strip()] = self._current_profile_values()
        try:
            self.profile_manager.save(self.profiles)
            self.profile_var.set(name.strip())
            self._refresh_profile_combo()
            self._save_settings_safely()
            self._log(f"Saved profile: {name.strip()}")
        except Exception as exc:
            self._log(f"ERROR: Could not save profile: {exc}")

    def delete_selected_profile(self) -> None:
        name = self.profile_var.get()
        if name in DEFAULT_PROFILES:
            messagebox.showinfo("Default Profile", "Default profiles cannot be deleted.")
            return
        if name not in self.profiles:
            return
        if not messagebox.askyesno("Delete Profile", f"Delete profile '{name}'?"):
            return
        self.profiles.pop(name, None)
        self.profile_manager.save(self.profiles)
        self._refresh_profile_combo()
        self._log(f"Deleted profile: {name}")

    def start_monitoring(self) -> None:
        self.monitor.start(ignore_current_clipboard=self.ignore_current_var.get())
        self.status_var.set("Running")
        self._save_settings_safely()

    def stop_all(self) -> None:
        self.typer.stop()
        self.monitor.stop()
        self.status_var.set("Stopped")
        self.progress_var.set("Progress: stopped")
        self.countdown_var.set("Countdown: idle")
        self._save_settings_safely()

    def emergency_stop(self) -> None:
        self.typer.stop()
        self.monitor.stop()
        self.clear_queue(confirm=False)
        self.status_var.set("Stopped")
        self.progress_var.set("Progress: stopped")
        self.countdown_var.set("Countdown: idle")
        self._log("Emergency stop: typing stopped, monitoring stopped, and queue cleared.")

    def toggle_pause_typing(self) -> None:
        self.typer.toggle_pause()
        self.progress_var.set("Progress: paused" if self.typer.is_paused else "Progress: resumed")

    def add_test_text(self) -> None:
        self._add_text_to_queue(config.TEST_TEXT, source="Test")
        self._log("Added built-in test text to queue.")

    def add_current_clipboard_to_queue(self) -> None:
        text = self._read_clipboard_text()
        if text is None:
            return
        self._add_text_to_queue(text, source="Clipboard button")

    def load_current_clipboard_to_preview(self) -> None:
        text = self._read_clipboard_text()
        if text is None:
            return
        self._set_preview_text(text)
        self._log("Loaded current clipboard text into preview.")

    def type_current_clipboard(self) -> None:
        text = self._read_clipboard_text()
        if text is None:
            return
        self.current_clipboard_text = text
        self._set_preview_text(text)
        self._request_typing(text)

    def type_selected_queue_item(self) -> None:
        item = self._selected_queue_item()
        if not item:
            if self.queue_items:
                item = self.queue_items[0]
                self.queue_listbox.selection_clear(0, tk.END)
                self.queue_listbox.selection_set(0)
            else:
                messagebox.showinfo("Queue Empty", "The typing queue is empty. Copy text or add the current clipboard first.")
                return
        self._set_preview_text(item.text)
        if self._request_typing(item.text):
            self._remove_queue_item_by_id(item.item_id)

    def type_preview_text(self) -> None:
        text = self.preview_text.get("1.0", tk.END)
        if text.endswith("\n"):
            text = text[:-1]
        self._request_typing(text)

    def edit_selected_queue_item(self) -> None:
        item = self._selected_queue_item()
        if not item:
            messagebox.showinfo("No Selection", "Select a queue item to edit.")
            return
        edited = self._open_edit_dialog(item.text, title="Edit Queue Item")
        if edited is None:
            return
        item.text = edited
        item.fingerprint = text_fingerprint(edited)
        self._refresh_queue_listbox(select_id=item.item_id)
        self._set_preview_text(edited)
        self._log(f"Edited queue item {item.item_id}.")

    def update_selected_from_preview(self) -> None:
        item = self._selected_queue_item()
        if not item:
            messagebox.showinfo("No Selection", "Select a queue item to update.")
            return
        text = self.preview_text.get("1.0", tk.END)
        if text.endswith("\n"):
            text = text[:-1]
        item.text = text
        item.fingerprint = text_fingerprint(text)
        self._refresh_queue_listbox(select_id=item.item_id)
        self._log(f"Updated queue item {item.item_id} from preview.")

    def remove_selected_queue_item(self) -> None:
        item = self._selected_queue_item()
        if not item:
            return
        self._remove_queue_item_by_id(item.item_id)
        self._log(f"Removed queue item {item.item_id}.")

    def clear_queue(self, confirm: bool = True) -> None:
        if confirm and self.queue_items and not messagebox.askyesno("Clear Queue", "Clear all queued clipboard items?"):
            return
        self.queue_items.clear()
        self._refresh_queue_listbox()
        self._update_queue_status()

    def _on_clipboard_text(self, event: ClipboardEvent) -> None:
        self.current_clipboard_text = event.text
        self._enqueue("preview", event.text)
        self._enqueue("add_queue", event)

    def _handle_clipboard_event(self, event: ClipboardEvent) -> None:
        added = self._add_text_to_queue(event.text, source="Clipboard", detected_at=datetime.fromtimestamp(event.detected_at))
        if added and self.auto_type_new_items_var.get():
            self.root.after(100, self.type_selected_queue_item)

    def _add_text_to_queue(self, text: str, source: str = "Clipboard", detected_at: Optional[datetime] = None) -> bool:
        if not text:
            self._log("WARNING: Empty clipboard text was ignored.")
            return False
        fingerprint = text_fingerprint(text)
        if self.ignore_duplicates_var.get():
            if fingerprint == self.last_typed_fingerprint or any(item.fingerprint == fingerprint for item in self.queue_items):
                self._log("Duplicate clipboard text ignored.")
                return False
        limit = self._get_queue_limit()
        while len(self.queue_items) >= limit:
            dropped = self.queue_items.pop(0)
            self._log(f"Queue limit reached. Dropped oldest item {dropped.item_id}.")
        item = QueueItem(
            item_id=self.next_queue_id,
            text=text,
            fingerprint=fingerprint,
            created_at=detected_at or datetime.now(),
            source=source,
        )
        self.next_queue_id += 1
        self.queue_items.append(item)
        self._refresh_queue_listbox(select_id=item.item_id)
        self._set_preview_text(text)
        self._update_queue_status()
        self._log(f"Queued {len(text)} character(s) from {source} as item {item.item_id}.")
        return True

    def _request_typing(self, text: str) -> bool:
        if not text:
            messagebox.showwarning("Empty Text", "There is no text to type.")
            return False
        final_text = text
        if self.edit_before_typing_var.get():
            edited = self._open_edit_dialog(final_text, title="Edit Before Typing")
            if edited is None:
                self._log("Typing cancelled from edit dialog.")
                return False
            final_text = edited
        if self.confirm_before_typing_var.get():
            preview = final_text[:500].replace("\r", "\\r").replace("\n", "\\n")
            message = f"Type this text into the active destination?\n\nCharacters: {len(final_text)}\nPreview: {preview}"
            if len(final_text) > 500:
                message += "..."
            if not messagebox.askyesno("Confirm Typing", message):
                self._log("Typing cancelled by user.")
                return False
        options = self._build_typing_options()
        if options is None:
            return False
        if self.typer.type_async(final_text, options):
            self.last_typed_fingerprint = text_fingerprint(final_text)
            self._save_settings_safely()
            return True
        return False

    def _open_edit_dialog(self, initial_text: str, title: str) -> Optional[str]:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.minsize(700, 450)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Review or edit the text. Click Type/Save to continue, or Cancel to stop.").pack(anchor=tk.W, padx=12, pady=(12, 4))
        text_widget = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Consolas", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        text_widget.insert(tk.END, initial_text)
        result: dict[str, Optional[str]] = {"value": None}

        def accept() -> None:
            value = text_widget.get("1.0", tk.END)
            if value.endswith("\n"):
                value = value[:-1]
            result["value"] = value
            dialog.destroy()

        def cancel() -> None:
            result["value"] = None
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Type / Save", command=accept).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text="Cancel", command=cancel).pack(side=tk.RIGHT)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(dialog)
        return result["value"]

    def _build_typing_options(self) -> Optional[TypingOptions]:
        cps = self._get_cps()
        delay = self._get_delay()
        min_delay, max_delay = self._get_random_delay_range()
        if cps is None or delay is None or min_delay is None or max_delay is None:
            return None
        return TypingOptions(
            characters_per_second=cps,
            initial_delay_seconds=delay,
            target_mode=self.target_mode_var.get(),
            insertion_mode=self.insertion_mode_var.get(),
            random_delay_enabled=self.random_delay_enabled_var.get(),
            random_delay_min_seconds=min_delay,
            random_delay_max_seconds=max_delay,
            restore_clipboard_after_paste=self.restore_clipboard_var.get(),
        )

    def _get_cps(self) -> Optional[int]:
        mode = self.speed_mode_var.get()
        if mode in config.SPEED_PRESETS:
            return int(config.SPEED_PRESETS[mode])
        try:
            cps = int(float(self.custom_cps_var.get()))
        except ValueError:
            self._log("ERROR: Custom CPS must be a number.")
            return None
        if cps < config.MIN_CPS or cps > config.MAX_CPS:
            self._log(f"ERROR: Custom CPS must be between {config.MIN_CPS} and {config.MAX_CPS}.")
            return None
        return cps

    def _get_delay(self) -> Optional[float]:
        try:
            delay = float(self.delay_var.get())
        except ValueError:
            self._log("ERROR: Start delay must be a number of seconds.")
            return None
        if delay < 0:
            self._log("ERROR: Start delay cannot be negative.")
            return None
        return delay

    def _get_random_delay_range(self) -> tuple[Optional[float], Optional[float]]:
        try:
            min_delay = float(self.random_delay_min_var.get())
            max_delay = float(self.random_delay_max_var.get())
        except ValueError:
            self._log("ERROR: Random delay min/max must be numbers.")
            return None, None
        if min_delay < config.MIN_RANDOM_DELAY_SECONDS or max_delay > config.MAX_RANDOM_DELAY_SECONDS:
            self._log(f"ERROR: Random delay must be between {config.MIN_RANDOM_DELAY_SECONDS} and {config.MAX_RANDOM_DELAY_SECONDS} seconds.")
            return None, None
        if min_delay > max_delay:
            self._log("ERROR: Random delay minimum cannot be greater than maximum.")
            return None, None
        return min_delay, max_delay

    def _get_queue_limit(self) -> int:
        try:
            limit = int(self.queue_limit_var.get())
        except ValueError:
            limit = config.DEFAULT_QUEUE_LIMIT
        return max(1, min(config.MAX_QUEUE_ITEMS, limit))

    def _selected_queue_item(self) -> Optional[QueueItem]:
        selection = self.queue_listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if 0 <= index < len(self.queue_items):
            return self.queue_items[index]
        return None

    def _remove_queue_item_by_id(self, item_id: int) -> None:
        self.queue_items = [item for item in self.queue_items if item.item_id != item_id]
        self._refresh_queue_listbox()
        self._update_queue_status()

    def _refresh_queue_listbox(self, select_id: Optional[int] = None) -> None:
        self.queue_listbox.delete(0, tk.END)
        selected_index = None
        for index, item in enumerate(self.queue_items):
            self.queue_listbox.insert(tk.END, item.display_label)
            if item.item_id == select_id:
                selected_index = index
        if selected_index is not None:
            self.queue_listbox.selection_set(selected_index)
            self.queue_listbox.see(selected_index)
        self._update_queue_status()

    def _preview_selected_queue_item(self) -> None:
        item = self._selected_queue_item()
        if item:
            self._set_preview_text(item.text)

    def _set_preview_text(self, text: str) -> None:
        display_text = text
        if len(display_text) > config.MAX_PREVIEW_CHARS:
            display_text = display_text[: config.MAX_PREVIEW_CHARS] + "\n\n[Preview truncated]"
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert(tk.END, display_text)

    def _update_queue_status(self) -> None:
        self.queue_status_var.set(f"Queue: {len(self.queue_items)} item(s)")

    def _read_clipboard_text(self) -> Optional[str]:
        if pyperclip is None:
            self._log("ERROR: pyperclip is not installed.")
            return None
        try:
            text = pyperclip.paste()
        except Exception as exc:
            self._log(f"ERROR: Could not read clipboard: {exc}")
            return None
        if not isinstance(text, str) or text == "":
            self._log("WARNING: Clipboard is empty or does not contain text.")
            return None
        return text

    def show_diagnostics(self) -> None:
        report = format_diagnostics()
        dialog = tk.Toplevel(self.root)
        dialog.title("Diagnostics")
        dialog.minsize(720, 420)
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        text.insert(tk.END, report)
        text.configure(state=tk.DISABLED)
        buttons = ttk.Frame(dialog)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Copy to Clipboard", command=lambda: self._copy_text_to_clipboard(report)).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)
        self._log("Diagnostics report opened.")

    def _copy_text_to_clipboard(self, text: str) -> None:
        if pyperclip is None:
            self._log("ERROR: pyperclip is not installed.")
            return
        try:
            pyperclip.copy(text)
            self._log("Copied report to clipboard.")
        except Exception as exc:
            self._log(f"ERROR: Could not copy to clipboard: {exc}")

    def export_log(self) -> None:
        content = self.log_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("No Log", "There is no log content to export.")
            return
        default_dir = app_data_dir() / "logs"
        default_dir.mkdir(parents=True, exist_ok=True)
        default_name = f"{config.LOG_EXPORT_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            title="Export Activity Log",
            initialdir=str(default_dir),
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(content, encoding="utf-8")
        self._log(f"Log exported to {path}")

    def clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _current_profile_values(self) -> dict[str, object]:
        return {
            "target_mode": self.target_mode_var.get(),
            "insertion_mode": self.insertion_mode_var.get(),
            "speed_mode": self.speed_mode_var.get(),
            "custom_cps": self.custom_cps_var.get(),
            "delay_seconds": self.delay_var.get(),
            "random_delay_enabled": self.random_delay_enabled_var.get(),
            "random_delay_min_seconds": self.random_delay_min_var.get(),
            "random_delay_max_seconds": self.random_delay_max_var.get(),
        }

    def _on_option_changed(self) -> None:
        self._apply_dark_mode()
        self._save_settings_safely()

    def _apply_dark_mode(self) -> None:
        if self.dark_mode_var.get():
            bg = "#1f1f1f"
            fg = "#f2f2f2"
            entry_bg = "#2b2b2b"
            self.root.configure(bg=bg)
            self.style.configure("TFrame", background=bg)
            self.style.configure("TLabelframe", background=bg, foreground=fg)
            self.style.configure("TLabelframe.Label", background=bg, foreground=fg)
            self.style.configure("TLabel", background=bg, foreground=fg)
            self.style.configure("TCheckbutton", background=bg, foreground=fg)
            try:
                self.preview_text.configure(bg=entry_bg, fg=fg, insertbackground=fg)
                self.log_text.configure(bg=entry_bg, fg=fg, insertbackground=fg)
                self.queue_listbox.configure(bg=entry_bg, fg=fg)
            except Exception:
                pass
        else:
            # Reset major widgets to platform defaults where practical.
            try:
                self.root.configure(bg=self.style.lookup("TFrame", "background"))
                self.preview_text.configure(bg="white", fg="black", insertbackground="black")
                self.log_text.configure(bg="white", fg="black", insertbackground="black")
                self.queue_listbox.configure(bg="white", fg="black")
            except Exception:
                pass

    def _register_shortcuts(self) -> None:
        """Register the safe command-mode hotkey.

        Only one global shortcut is registered: Ctrl+Alt+Insert. It opens a
        small app-owned popup with clickable buttons. No second letter key is
        registered globally, so letters such as S, T, P, Q, H, and E will not
        leak into Word, Google Docs, or browser fields.
        """
        self.root.bind(config.LOCAL_COMMAND_MODE_HOTKEY, lambda _event: self.show_command_mode_popup())
        self.root.bind(config.LOCAL_SHORTCUTS["emergency_stop"], lambda _event: self.emergency_stop())

        if keyboard is None:
            self.shortcut_status_var.set("Command Mode: local only")
            self._log(
                "Global keyboard library is unavailable. Command Mode can still be opened while the app window is focused with "
                f"{config.COMMAND_MODE_HOTKEY_LABEL}."
            )
            return

        try:
            hotkey_handle = keyboard.add_hotkey(
                config.COMMAND_MODE_HOTKEY,
                lambda: self.root.after(0, self.show_command_mode_popup),
                suppress=True,
                trigger_on_release=True,
            )
            self.hotkey_registered_names.append(hotkey_handle)
            self.shortcut_status_var.set(f"Command Mode: {config.COMMAND_MODE_HOTKEY_LABEL}")
            self._log(
                f"Command Mode registered. Press {config.COMMAND_MODE_HOTKEY_LABEL} to open the control popup. "
                "No action letters are captured globally, so commands should not type into Word or Google Docs."
            )
        except Exception as exc:
            self.shortcut_status_var.set("Command Mode: registration failed")
            self._log(f"WARNING: Could not register Command Mode hotkey {config.COMMAND_MODE_HOTKEY_LABEL}: {exc}")

    def show_command_mode_popup(self) -> str:
        """Show a compact command popup for safe click-based control."""
        if self.exiting:
            return "break"

        # Reuse the same popup when possible. In earlier command-mode builds,
        # the Close button destroyed the Toplevel window. Some Windows/Tk builds
        # can leave a stale reference behind, so the next global hotkey appears
        # to do nothing. This version treats Close as Hide/Withdraw and only
        # clears the reference if Windows actually destroys the popup.
        if self.command_popup is not None:
            try:
                if self.command_popup.winfo_exists():
                    self.command_popup.deiconify()
                    self.command_popup.attributes("-topmost", True)
                    self.command_popup.lift()
                    self.command_popup.after(50, self.command_popup.focus_force)
                    self._log("Command Mode reopened.")
                    return "break"
            except tk.TclError:
                self.command_popup = None

        popup = tk.Toplevel(self.root)
        self.command_popup = popup
        popup.title("Clipboard Auto Typer - Command Mode")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        # Only make the popup transient when the main window is visible. If the
        # main window is hidden to tray, transient popups may also stay hidden
        # or fail to come back on some Windows setups.
        try:
            if self.root.state() != "withdrawn" and self.root.winfo_viewable():
                popup.transient(self.root)
        except Exception:
            pass

        def close_popup() -> str:
            """Hide the command popup without destroying its hotkey state."""
            try:
                if self.command_popup is not None and self.command_popup.winfo_exists():
                    self.command_popup.withdraw()
                    self._log("Command Mode hidden. Press Ctrl + Alt + Insert to reopen it.")
            except tk.TclError:
                self.command_popup = None
            return "break"

        def cleanup_popup_reference(_event: tk.Event | None = None) -> None:
            # Clear the reference only when the command popup itself is
            # destroyed, not when child buttons/frames are destroyed.
            try:
                if self.command_popup is not None and _event is not None and _event.widget is self.command_popup:
                    self.command_popup = None
            except Exception:
                self.command_popup = None

        popup.protocol("WM_DELETE_WINDOW", close_popup)
        popup.bind("<Escape>", lambda _event: close_popup())
        popup.bind("<Destroy>", cleanup_popup_reference, add="+")

        container = ttk.Frame(popup, padding=14)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text="Command Mode",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
        ttk.Label(
            container,
            text="Choose an action below. This popup avoids shortcut letters being sent to Word, Google Docs, or your browser.",
            wraplength=420,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        def run_and_close(action: str) -> None:
            close_popup()
            self._execute_shortcut_action(action)

        buttons = [
            ("Start Monitoring", "start"),
            ("Stop + Clear Queue", "stop"),
            ("Pause / Resume", "pause_resume"),
            ("Type Selected Queue Item", "type_selected"),
            ("Type Current Clipboard", "type_current"),
            ("Show / Hide Main Window", "show_hide"),
            ("Emergency Stop", "emergency_stop"),
        ]
        for index, (label, action) in enumerate(buttons):
            row = 2 + index // 2
            col = index % 2
            ttk.Button(
                container,
                text=label,
                width=28,
                command=lambda action=action: run_and_close(action),
            ).grid(row=row, column=col, sticky=tk.EW, padx=(0 if col == 0 else 8, 0), pady=4)

        ttk.Separator(container).grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(10, 8))
        ttk.Button(container, text="Close / Hide Popup", command=close_popup).grid(row=7, column=0, columnspan=2, sticky=tk.EW)

        for col in range(2):
            container.columnconfigure(col, weight=1)

        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        x = max(0, int((screen_w - width) / 2))
        y = max(0, int((screen_h - height) / 3))
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()
        popup.lift()
        popup.after(50, popup.focus_force)
        self._log("Command Mode opened. Use Close / Hide Popup to hide it; press Ctrl + Alt + Insert to reopen.")
        return "break"

    def _execute_shortcut_action(self, action: str) -> None:
        actions: dict[str, Callable[[], None]] = {
            "start": self.start_monitoring,
            "stop": self.emergency_stop,
            "pause_resume": self.toggle_pause_typing,
            "type_selected": self.type_selected_queue_item,
            "type_current": self.type_current_clipboard,
            "show_hide": self.toggle_window_visibility,
            "emergency_stop": self.emergency_stop,
        }
        callback = actions.get(action)
        if callback is None:
            self._log(f"WARNING: Unknown Command Mode action: {action}")
            return
        callback()

    def _unregister_shortcuts(self) -> None:
        if keyboard is None:
            return
        for hotkey in self.hotkey_registered_names:
            try:
                keyboard.remove_hotkey(hotkey)
            except Exception:
                pass
        self.hotkey_registered_names.clear()

    def _setup_tray_icon(self) -> None:
        if pystray is None or Image is None or ImageDraw is None:
            self.tray_status_var.set("Tray: unavailable")
            self._log("Tray support unavailable. Install pystray and Pillow for minimize-to-tray.")
            return
        image = self._create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show Clipboard Auto Typer", lambda _icon, _item: self.root.after(0, self.show_window)),
            pystray.MenuItem("Start Monitoring", lambda _icon, _item: self.root.after(0, self.start_monitoring)),
            pystray.MenuItem("Stop + Clear Queue", lambda _icon, _item: self.root.after(0, self.emergency_stop)),
            pystray.MenuItem("Pause/Resume", lambda _icon, _item: self.root.after(0, self.toggle_pause_typing)),
            pystray.MenuItem("Type Selected", lambda _icon, _item: self.root.after(0, self.type_selected_queue_item)),
            pystray.MenuItem("Type Current Clipboard", lambda _icon, _item: self.root.after(0, self.type_current_clipboard)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", lambda _icon, _item: self.root.after(0, self.confirm_exit)),
        )
        self.tray_icon = pystray.Icon(config.APP_ID, image, config.APP_NAME, menu)
        self.tray_thread = threading.Thread(target=self.tray_icon.run, name="TrayIcon", daemon=True)
        self.tray_thread.start()
        self.tray_status_var.set("Tray: active")
        self._log("System tray icon started. Minimize the window to move it to the tray.")

    @staticmethod
    def _create_tray_image():
        size = 64
        image = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=8, outline="black", width=4)
        draw.rectangle((18, 16, 46, 22), fill="black")
        draw.rectangle((18, 30, 46, 36), fill="black")
        draw.rectangle((18, 44, 38, 50), fill="black")
        return image

    def _on_window_unmap(self, _event) -> None:
        if self.exiting or not self.minimize_to_tray_var.get() or pystray is None:
            return
        if self._minimize_event_in_progress:
            return
        self._minimize_event_in_progress = True
        self.root.after(150, self._hide_if_minimized)

    def _hide_if_minimized(self) -> None:
        try:
            if not self.exiting and self.root.state() == "iconic" and self.minimize_to_tray_var.get():
                self.root.withdraw()
                self._log("Window minimized to system tray.")
        finally:
            self._minimize_event_in_progress = False

    def hide_to_tray(self) -> None:
        if pystray is None:
            self.root.iconify()
            return
        self.root.withdraw()
        self._log("Window hidden to system tray.")

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def toggle_window_visibility(self) -> None:
        if self.root.state() == "withdrawn" or not self.root.winfo_viewable():
            self.show_window()
        else:
            self.hide_to_tray()

    def _schedule_queue_processing(self) -> None:
        self._process_queue()
        self.root.after(100, self._schedule_queue_processing)

    def _process_queue(self) -> None:
        while True:
            try:
                item_type, value = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            if item_type == "log":
                self._log(str(value))
            elif item_type == "preview":
                self._set_preview_text(str(value))
            elif item_type == "add_queue":
                self._handle_clipboard_event(value)  # type: ignore[arg-type]
            elif item_type == "progress":
                current, total = value  # type: ignore[misc]
                self.progress_var.set(f"Progress: {current}/{total}")
            elif item_type == "countdown":
                seconds = float(value)
                if seconds > 0:
                    self.countdown_var.set(f"Countdown: {seconds:.1f}s")
                else:
                    self.countdown_var.set("Countdown: idle")
            elif item_type == "done":
                success, message = value  # type: ignore[misc]
                self._log(("SUCCESS: " if success else "WARNING: ") + str(message))
                self.progress_var.set("Progress: complete" if success else "Progress: stopped")
                self.countdown_var.set("Countdown: idle")

    def _schedule_target_status_update(self) -> None:
        ready, message = TargetDetector.readiness_message(self.target_mode_var.get())
        self.target_status_var.set(("Ready - " if ready else "Not ready - ") + message)
        self.root.after(1000, self._schedule_target_status_update)

    def _enqueue(self, item_type: str, value: object) -> None:
        self.ui_queue.put((item_type, value))

    def _log(self, message: str) -> None:
        if not hasattr(self, "log_text"):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self._trim_log()
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _trim_log(self) -> None:
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > config.MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{line_count - config.MAX_LOG_LINES}.0")

    def _save_settings_safely(self) -> None:
        settings = {
            "speed_mode": self.speed_mode_var.get(),
            "custom_cps": self.custom_cps_var.get(),
            "delay_seconds": self.delay_var.get(),
            "target_mode": self.target_mode_var.get(),
            "insertion_mode": self.insertion_mode_var.get(),
            "random_delay_enabled": self.random_delay_enabled_var.get(),
            "random_delay_min_seconds": self.random_delay_min_var.get(),
            "random_delay_max_seconds": self.random_delay_max_var.get(),
            "ignore_current_clipboard_on_start": self.ignore_current_var.get(),
            "minimize_to_tray": self.minimize_to_tray_var.get(),
            "confirm_before_typing": self.confirm_before_typing_var.get(),
            "edit_before_typing": self.edit_before_typing_var.get(),
            "ignore_duplicates": self.ignore_duplicates_var.get(),
            "restore_clipboard_after_paste": self.restore_clipboard_var.get(),
            "dark_mode": self.dark_mode_var.get(),
            "queue_limit": self.queue_limit_var.get(),
            "auto_type_new_items": self.auto_type_new_items_var.get(),
            "active_profile": self.profile_var.get(),
        }
        try:
            self.settings_manager.save(settings)
        except Exception as exc:
            self._log(f"WARNING: Could not save settings: {exc}")

    def confirm_exit(self) -> None:
        if self.typer.is_typing:
            if not messagebox.askyesno("Typing in Progress", "Typing is in progress. Stop and exit?"):
                return
        self.exiting = True
        self._save_settings_safely()
        self.typer.stop()
        self.monitor.stop()
        self._unregister_shortcuts()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    ClipboardAutoTyperApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_app()
