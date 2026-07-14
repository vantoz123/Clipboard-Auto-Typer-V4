"""Typing profile storage.

Profiles contain only app preferences. They never contain clipboard text.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import config
from settings_manager import app_data_dir


DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "Word - Exact": {
        "target_mode": config.TARGET_MODE_WORD,
        "insertion_mode": config.INSERTION_MODE_SAFE_WORD,
        "speed_mode": "Normal",
        "custom_cps": 25,
        "delay_seconds": 3.0,
        "random_delay_enabled": False,
        "random_delay_min_seconds": 0.01,
        "random_delay_max_seconds": 0.05,
    },
    "Word - Natural Type": {
        "target_mode": config.TARGET_MODE_WORD,
        "insertion_mode": config.INSERTION_MODE_WORD_HUMAN,
        "speed_mode": "Slow",
        "custom_cps": 5,
        "delay_seconds": 3.0,
        "random_delay_enabled": True,
        "random_delay_min_seconds": 0.01,
        "random_delay_max_seconds": 0.05,
    },
    "Google Docs - Exact Paste": {
        "target_mode": config.TARGET_MODE_GOOGLE_DOCS,
        "insertion_mode": config.INSERTION_MODE_BROWSER_PASTE,
        "speed_mode": "Normal",
        "custom_cps": 25,
        "delay_seconds": 3.0,
        "random_delay_enabled": False,
        "random_delay_min_seconds": 0.01,
        "random_delay_max_seconds": 0.05,
    },
    "Google Docs - Natural Type": {
        "target_mode": config.TARGET_MODE_GOOGLE_DOCS,
        "insertion_mode": config.INSERTION_MODE_BROWSER_HUMAN,
        "speed_mode": "Slow",
        "custom_cps": 5,
        "delay_seconds": 3.0,
        "random_delay_enabled": True,
        "random_delay_min_seconds": 0.01,
        "random_delay_max_seconds": 0.05,
    },
}


class ProfileManager:
    """Loads and saves typing profiles."""

    def __init__(self) -> None:
        self.profile_dir = app_data_dir()
        self.profile_path = self.profile_dir / config.PROFILES_FILENAME

    def load(self) -> Dict[str, Dict[str, Any]]:
        profiles = {name: dict(values) for name, values in DEFAULT_PROFILES.items()}
        try:
            if self.profile_path.exists():
                raw = json.loads(self.profile_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for name, values in raw.items():
                        if isinstance(values, dict):
                            profiles[str(name)] = self._sanitize(values)
        except Exception:
            return profiles
        return profiles

    def save(self, profiles: Dict[str, Dict[str, Any]]) -> None:
        clean = {str(name): self._sanitize(values) for name, values in profiles.items() if str(name).strip()}
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(json.dumps(clean, indent=2), encoding="utf-8")

    @staticmethod
    def _sanitize(values: Dict[str, Any]) -> Dict[str, Any]:
        target = str(values.get("target_mode", config.DEFAULT_TARGET_MODE))
        insertion = str(values.get("insertion_mode", config.DEFAULT_INSERTION_MODE))
        speed = str(values.get("speed_mode", config.DEFAULT_SPEED_MODE))
        try:
            cps = int(values.get("custom_cps", config.SPEED_PRESETS[config.DEFAULT_SPEED_MODE]))
        except (TypeError, ValueError):
            cps = config.SPEED_PRESETS[config.DEFAULT_SPEED_MODE]
        try:
            delay = float(values.get("delay_seconds", config.DEFAULT_DELAY_SECONDS))
        except (TypeError, ValueError):
            delay = config.DEFAULT_DELAY_SECONDS
        try:
            min_delay = float(values.get("random_delay_min_seconds", config.DEFAULT_RANDOM_DELAY_MIN_SECONDS))
        except (TypeError, ValueError):
            min_delay = config.DEFAULT_RANDOM_DELAY_MIN_SECONDS
        try:
            max_delay = float(values.get("random_delay_max_seconds", config.DEFAULT_RANDOM_DELAY_MAX_SECONDS))
        except (TypeError, ValueError):
            max_delay = config.DEFAULT_RANDOM_DELAY_MAX_SECONDS
        min_delay = max(config.MIN_RANDOM_DELAY_SECONDS, min(config.MAX_RANDOM_DELAY_SECONDS, min_delay))
        max_delay = max(config.MIN_RANDOM_DELAY_SECONDS, min(config.MAX_RANDOM_DELAY_SECONDS, max_delay))
        if min_delay > max_delay:
            min_delay, max_delay = max_delay, min_delay
        return {
            "target_mode": target if target in config.TARGET_MODES else config.DEFAULT_TARGET_MODE,
            "insertion_mode": insertion if insertion in config.INSERTION_MODES else config.DEFAULT_INSERTION_MODE,
            "speed_mode": speed if speed in (*config.SPEED_PRESETS.keys(), "Custom") else config.DEFAULT_SPEED_MODE,
            "custom_cps": max(config.MIN_CPS, min(config.MAX_CPS, cps)),
            "delay_seconds": max(0.0, delay),
            "random_delay_enabled": bool(values.get("random_delay_enabled", config.DEFAULT_RANDOM_DELAY_ENABLED)),
            "random_delay_min_seconds": min_delay,
            "random_delay_max_seconds": max_delay,
        }
