"""Active application detection for Word and browser targets."""

from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Optional, Tuple

import psutil

import config


@dataclass(frozen=True)
class ActiveWindowInfo:
    hwnd: int
    title: str
    process_id: int
    process_name: str

    @property
    def normalized_process_name(self) -> str:
        return self.process_name.lower().strip()

    @property
    def normalized_title(self) -> str:
        return self.title.lower().strip()


class TargetDetector:
    """Detects whether supported typing destinations are available and active."""

    WORD_PROCESS_NAME = "winword.exe"

    @staticmethod
    def is_windows() -> bool:
        return platform.system().lower() == "windows"

    @classmethod
    def is_word_running(cls) -> bool:
        if not cls.is_windows():
            return False
        for process in psutil.process_iter(attrs=["name"]):
            try:
                name = (process.info.get("name") or "").lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if name == cls.WORD_PROCESS_NAME:
                return True
        return False

    @classmethod
    def active_window_info(cls) -> Optional[ActiveWindowInfo]:
        if not cls.is_windows():
            return None
        try:
            import win32gui
            import win32process

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = ""
            try:
                process_name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = ""
            return ActiveWindowInfo(hwnd=hwnd, title=title, process_id=pid, process_name=process_name)
        except Exception:
            return None

    @classmethod
    def is_word_active(cls) -> bool:
        info = cls.active_window_info()
        if not info:
            return False
        return info.normalized_process_name == cls.WORD_PROCESS_NAME or "word" in info.normalized_title

    @classmethod
    def is_supported_browser_active(cls) -> bool:
        info = cls.active_window_info()
        if not info:
            return False
        if info.normalized_process_name in config.SUPPORTED_BROWSER_PROCESSES:
            return True
        # Many Chromium profile/browser wrappers still include useful title hints.
        return any(hint in info.normalized_title for hint in config.GOOGLE_DOCS_TITLE_HINTS)

    @classmethod
    def is_google_docs_likely_active(cls) -> bool:
        info = cls.active_window_info()
        if not info:
            return False
        title = info.normalized_title
        return cls.is_supported_browser_active() and any(hint in title for hint in config.GOOGLE_DOCS_TITLE_HINTS)

    @classmethod
    def get_active_word_application(cls):
        if not cls.is_windows():
            raise RuntimeError("Microsoft Word integration is available only on Windows.")
        try:
            import win32com.client

            return win32com.client.GetActiveObject("Word.Application")
        except Exception as exc:
            raise RuntimeError("Microsoft Word is not running or cannot be accessed.") from exc

    @classmethod
    def active_document_name(cls) -> str:
        if not cls.is_windows() or not cls.is_word_running():
            return ""
        try:
            import pythoncom

            pythoncom.CoInitialize()
            try:
                word_app = cls.get_active_word_application()
                doc = getattr(word_app, "ActiveDocument", None)
                return str(getattr(doc, "Name", "") or "")
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            return ""

    @classmethod
    def active_window_summary(cls) -> str:
        info = cls.active_window_info()
        if not info:
            return "No active window detected"
        title = info.title or "Untitled window"
        process = info.process_name or "unknown process"
        return f"{title} ({process})"

    @classmethod
    def readiness_message(cls, target_mode: str = config.TARGET_MODE_AUTO) -> Tuple[bool, str]:
        if not cls.is_windows():
            return False, "This app must be run on Windows for active-window detection."

        info = cls.active_window_info()
        if target_mode == config.TARGET_MODE_WORD:
            if not cls.is_word_running():
                return False, "Microsoft Word is not running. Open Word and a document first."
            if not cls.is_word_active():
                doc_name = cls.active_document_name()
                if doc_name:
                    return False, f"Word is running ({doc_name}) but is not active. Click inside the document."
                return False, "Microsoft Word is running but is not active. Click inside the target document."
            doc_name = cls.active_document_name()
            return True, f"Word active: {doc_name}" if doc_name else "Microsoft Word is active."

        if target_mode == config.TARGET_MODE_GOOGLE_DOCS:
            if cls.is_google_docs_likely_active():
                return True, "Google Docs appears active in the browser."
            if cls.is_supported_browser_active():
                title = info.title if info else "browser"
                return True, f"Browser is active: {title}. Click inside Google Docs before typing."
            return False, "No supported browser is active. Open Google Docs and click inside the document."

        if cls.is_word_active():
            return True, "Auto detect: Microsoft Word is active."
        if cls.is_google_docs_likely_active():
            return True, "Auto detect: Google Docs appears active."
        if cls.is_supported_browser_active():
            return True, "Auto detect: supported browser is active. Click inside Google Docs before typing."
        return False, "Auto detect: open Word or Google Docs, then click inside the target document."
