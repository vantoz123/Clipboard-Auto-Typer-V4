"""Settings helper for non-sensitive user preferences.

Only UI and behavior preferences are stored. Clipboard text and typed content are
never written to disk by this module.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import config


def app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / config.APP_ID
    return Path.home() / f".{config.APP_ID}"


DEFAULT_SETTINGS: Dict[str, Any] = {
    "speed_mode": config.DEFAULT_SPEED_MODE,
    "custom_cps": config.SPEED_PRESETS[config.DEFAULT_SPEED_MODE],
    "delay_seconds": config.DEFAULT_DELAY_SECONDS,
    "target_mode": config.DEFAULT_TARGET_MODE,
    "insertion_mode": config.DEFAULT_INSERTION_MODE,
    "random_delay_enabled": config.DEFAULT_RANDOM_DELAY_ENABLED,
    "random_delay_min_seconds": config.DEFAULT_RANDOM_DELAY_MIN_SECONDS,
    "random_delay_max_seconds": config.DEFAULT_RANDOM_DELAY_MAX_SECONDS,
    "ignore_current_clipboard_on_start": True,
    "minimize_to_tray": config.DEFAULT_MINIMIZE_TO_TRAY,
    "confirm_before_typing": config.DEFAULT_CONFIRM_BEFORE_TYPING,
    "edit_before_typing": config.DEFAULT_EDIT_BEFORE_TYPING,
    "ignore_duplicates": config.DEFAULT_IGNORE_DUPLICATES,
    "restore_clipboard_after_paste": config.DEFAULT_RESTORE_CLIPBOARD_AFTER_PASTE,
    "dark_mode": config.DEFAULT_DARK_MODE,
    "queue_limit": config.DEFAULT_QUEUE_LIMIT,
    "auto_type_new_items": config.DEFAULT_AUTO_TYPE_NEW_ITEMS,
    "active_profile": "Word - Exact",
}


class SettingsManager:
    """Loads and saves non-sensitive settings."""

    def __init__(self) -> None:
        self.settings_dir = app_data_dir()
        self.settings_path = self.settings_dir / config.SETTINGS_FILENAME

    def load(self) -> Dict[str, Any]:
        settings = dict(DEFAULT_SETTINGS)
        try:
            if self.settings_path.exists():
                raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    settings.update(raw)
        except Exception:
            return settings
        return self._sanitize(settings)

    def save(self, settings: Dict[str, Any]) -> None:
        clean = self._sanitize(settings)
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(clean, indent=2), encoding="utf-8")

    @staticmethod
    def _sanitize(settings: Dict[str, Any]) -> Dict[str, Any]:
        clean = dict(DEFAULT_SETTINGS)

        speed_mode = str(settings.get("speed_mode", clean["speed_mode"]))
        clean["speed_mode"] = speed_mode if speed_mode in (*config.SPEED_PRESETS.keys(), "Custom") else config.DEFAULT_SPEED_MODE

        try:
            cps = int(settings.get("custom_cps", clean["custom_cps"]))
        except (TypeError, ValueError):
            cps = int(DEFAULT_SETTINGS["custom_cps"])
        clean["custom_cps"] = max(config.MIN_CPS, min(config.MAX_CPS, cps))

        try:
            delay = float(settings.get("delay_seconds", clean["delay_seconds"]))
        except (TypeError, ValueError):
            delay = float(DEFAULT_SETTINGS["delay_seconds"])
        clean["delay_seconds"] = max(0.0, delay)

        target_mode = str(settings.get("target_mode", clean["target_mode"]))
        clean["target_mode"] = target_mode if target_mode in config.TARGET_MODES else config.DEFAULT_TARGET_MODE

        insertion_mode = str(settings.get("insertion_mode", clean["insertion_mode"]))
        clean["insertion_mode"] = insertion_mode if insertion_mode in config.INSERTION_MODES else config.DEFAULT_INSERTION_MODE

        clean["random_delay_enabled"] = bool(settings.get("random_delay_enabled", config.DEFAULT_RANDOM_DELAY_ENABLED))

        def clamp_delay(value: Any, default: float) -> float:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = default
            return max(config.MIN_RANDOM_DELAY_SECONDS, min(config.MAX_RANDOM_DELAY_SECONDS, number))

        min_delay = clamp_delay(
            settings.get("random_delay_min_seconds", clean["random_delay_min_seconds"]),
            config.DEFAULT_RANDOM_DELAY_MIN_SECONDS,
        )
        max_delay = clamp_delay(
            settings.get("random_delay_max_seconds", clean["random_delay_max_seconds"]),
            config.DEFAULT_RANDOM_DELAY_MAX_SECONDS,
        )
        if min_delay > max_delay:
            min_delay, max_delay = max_delay, min_delay
        clean["random_delay_min_seconds"] = min_delay
        clean["random_delay_max_seconds"] = max_delay

        clean["ignore_current_clipboard_on_start"] = bool(settings.get("ignore_current_clipboard_on_start", True))
        clean["minimize_to_tray"] = bool(settings.get("minimize_to_tray", config.DEFAULT_MINIMIZE_TO_TRAY))
        clean["confirm_before_typing"] = bool(settings.get("confirm_before_typing", config.DEFAULT_CONFIRM_BEFORE_TYPING))
        clean["edit_before_typing"] = bool(settings.get("edit_before_typing", config.DEFAULT_EDIT_BEFORE_TYPING))
        clean["ignore_duplicates"] = bool(settings.get("ignore_duplicates", config.DEFAULT_IGNORE_DUPLICATES))
        clean["restore_clipboard_after_paste"] = bool(settings.get("restore_clipboard_after_paste", config.DEFAULT_RESTORE_CLIPBOARD_AFTER_PASTE))
        clean["dark_mode"] = bool(settings.get("dark_mode", config.DEFAULT_DARK_MODE))

        try:
            queue_limit = int(settings.get("queue_limit", config.DEFAULT_QUEUE_LIMIT))
        except (TypeError, ValueError):
            queue_limit = config.DEFAULT_QUEUE_LIMIT
        clean["queue_limit"] = max(1, min(config.MAX_QUEUE_ITEMS, queue_limit))
        clean["auto_type_new_items"] = bool(settings.get("auto_type_new_items", config.DEFAULT_AUTO_TYPE_NEW_ITEMS))

        clean["active_profile"] = str(settings.get("active_profile", clean["active_profile"])) or "Word - Exact"
        return clean
