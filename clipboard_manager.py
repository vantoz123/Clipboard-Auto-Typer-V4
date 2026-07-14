"""Clipboard monitoring utilities.

The monitor reads text from the system clipboard without writing anything back to
it. Paste mode may temporarily write to the clipboard only when exact insertion
of edited/queued text is requested; that behavior is controlled in typer_engine.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import pyperclip

import config


@dataclass(frozen=True)
class ClipboardEvent:
    """Represents newly detected text clipboard content."""

    text: str
    length: int
    detected_at: float
    fingerprint: str


def text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class ClipboardMonitor:
    """Polls the system clipboard and reports newly copied text."""

    def __init__(
        self,
        interval_seconds: float = config.CLIPBOARD_POLL_INTERVAL,
        on_text: Optional[Callable[[ClipboardEvent], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.interval_seconds = max(0.10, interval_seconds)
        self.on_text = on_text
        self.on_error = on_error
        self.on_status = on_status
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_fingerprint: Optional[str] = None
        self._last_error_message: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, ignore_current_clipboard: bool = True) -> None:
        if self.is_running:
            self._emit_status("Clipboard monitor is already running.")
            return
        if ignore_current_clipboard:
            try:
                text = self.get_current_text()
                self._last_fingerprint = text_fingerprint(text) if text else None
            except Exception:
                self._last_fingerprint = None
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="ClipboardMonitor", daemon=True)
        self._thread.start()
        self._emit_status("Clipboard monitoring started.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._emit_status("Clipboard monitoring stopped.")

    def reset_last_seen(self) -> None:
        self._last_fingerprint = None

    @staticmethod
    def get_current_text() -> str:
        value = pyperclip.paste()
        if value is None:
            return ""
        if not isinstance(value, str):
            raise TypeError("Clipboard content is not text.")
        return value

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self.get_current_text()
                self._last_error_message = None
            except Exception as exc:
                message = f"Unable to read clipboard text: {exc}"
                if message != self._last_error_message:
                    self._emit_error(message)
                    self._last_error_message = message
                time.sleep(self.interval_seconds)
                continue

            if text:
                fingerprint = text_fingerprint(text)
                if fingerprint != self._last_fingerprint:
                    self._last_fingerprint = fingerprint
                    if self.on_text:
                        self.on_text(ClipboardEvent(text=text, length=len(text), detected_at=time.time(), fingerprint=fingerprint))
            elif self._last_fingerprint is None:
                self._last_fingerprint = ""

            time.sleep(self.interval_seconds)

    def _emit_error(self, message: str) -> None:
        if self.on_error:
            self.on_error(message)

    def _emit_status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)
