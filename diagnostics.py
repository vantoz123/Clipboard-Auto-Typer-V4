"""Diagnostics for Clipboard Auto Typer."""

from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass
from typing import List

import config
from target_detector import TargetDetector


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    status: str
    detail: str


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def run_diagnostics() -> List[DiagnosticResult]:
    results: List[DiagnosticResult] = []
    is_windows = TargetDetector.is_windows()
    results.append(DiagnosticResult("Operating system", "OK" if is_windows else "WARNING", platform.platform()))
    py_ok = sys.version_info >= (3, 9)
    results.append(DiagnosticResult("Python version", "OK" if py_ok else "WARNING", sys.version.replace("\n", " ")))

    for module_name, friendly in (
        ("pyperclip", "Clipboard access"),
        ("pyautogui", "Browser typing"),
        ("psutil", "Process detection"),
        ("win32com.client", "Microsoft Word COM"),
        ("win32gui", "Active window detection"),
        ("keyboard", "Global shortcuts"),
        ("pystray", "System tray"),
        ("PIL", "Tray icon graphics"),
    ):
        available = _module_available(module_name)
        results.append(DiagnosticResult(friendly, "OK" if available else "MISSING", f"Python module: {module_name}"))

    if is_windows:
        results.append(DiagnosticResult("Microsoft Word running", "OK" if TargetDetector.is_word_running() else "INFO", "Open Word to use Word modes."))
        ready, message = TargetDetector.readiness_message(config.TARGET_MODE_AUTO)
        results.append(DiagnosticResult("Active target", "OK" if ready else "INFO", message))
    else:
        results.append(DiagnosticResult("Windows integrations", "WARNING", "Word and active-window detection require Windows."))
    return results


def format_diagnostics() -> str:
    lines = [f"{config.APP_NAME} v{config.APP_VERSION} diagnostics", "=" * 48]
    for result in run_diagnostics():
        lines.append(f"[{result.status}] {result.name}: {result.detail}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_diagnostics())
