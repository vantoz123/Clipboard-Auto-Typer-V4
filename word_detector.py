"""Backward-compatible Word detection wrapper.

New code should use target_detector.TargetDetector directly.
"""

from __future__ import annotations

from target_detector import TargetDetector


def is_word_running() -> bool:
    return TargetDetector.is_word_running()


def is_word_active() -> bool:
    return TargetDetector.is_word_active()


def active_document_name() -> str:
    return TargetDetector.active_document_name()
