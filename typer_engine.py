"""Typing engine for inserting clipboard text into Word or Google Docs/browser.

Word exact mode uses Microsoft Word COM automation. Google Docs/browser exact
mode uses Ctrl+V and can temporarily place edited/queued text on the clipboard,
then restore the previous clipboard text.

Browser Human Type in v4.1 is hybrid Unicode mode: common keyboard characters
are typed key-by-key with natural delay, while Unicode/accent/emoji clusters are
inserted through a short temporary clipboard paste and the original clipboard is
restored when possible.
"""

from __future__ import annotations

import random
import string
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple

import pyperclip

import config
from target_detector import TargetDetector


LogCallback = Callable[[str], None]
DoneCallback = Callable[[bool, str], None]
ProgressCallback = Callable[[int, int], None]
CountdownCallback = Callable[[float], None]


@dataclass(frozen=True)
class TypingOptions:
    characters_per_second: int
    initial_delay_seconds: float
    target_mode: str = config.DEFAULT_TARGET_MODE
    insertion_mode: str = config.DEFAULT_INSERTION_MODE
    require_active_target: bool = True
    random_delay_enabled: bool = config.DEFAULT_RANDOM_DELAY_ENABLED
    random_delay_min_seconds: float = config.DEFAULT_RANDOM_DELAY_MIN_SECONDS
    random_delay_max_seconds: float = config.DEFAULT_RANDOM_DELAY_MAX_SECONDS
    restore_clipboard_after_paste: bool = config.DEFAULT_RESTORE_CLIPBOARD_AFTER_PASTE


class AutoCorrectGuard:
    """Temporarily disables common Word AutoFormat-as-you-type mutations."""

    OPTION_NAMES: Iterable[str] = (
        "AutoFormatAsYouTypeReplaceQuotes",
        "AutoFormatAsYouTypeReplaceSymbols",
        "AutoFormatAsYouTypeReplaceOrdinals",
        "AutoFormatAsYouTypeReplaceFractions",
        "AutoFormatAsYouTypeReplacePlainTextEmphasis",
        "AutoFormatAsYouTypeApplyHeadings",
        "AutoFormatAsYouTypeApplyBorders",
        "AutoFormatAsYouTypeApplyBulletedLists",
        "AutoFormatAsYouTypeApplyNumberedLists",
        "AutoFormatAsYouTypeDefineStyles",
        "AutoFormatAsYouTypeFormatListItemBeginning",
    )
    AUTOCORRECT_NAMES: Iterable[str] = ("ReplaceText",)

    def __init__(self, word_app) -> None:
        self.word_app = word_app
        self._saved_options: Dict[str, object] = {}
        self._saved_autocorrect: Dict[str, object] = {}

    def __enter__(self):
        options = getattr(self.word_app, "Options", None)
        if options is not None:
            for name in self.OPTION_NAMES:
                try:
                    current = getattr(options, name)
                    self._saved_options[name] = current
                    setattr(options, name, False)
                except Exception:
                    continue
        autocorrect = getattr(self.word_app, "AutoCorrect", None)
        if autocorrect is not None:
            for name in self.AUTOCORRECT_NAMES:
                try:
                    current = getattr(autocorrect, name)
                    self._saved_autocorrect[name] = current
                    setattr(autocorrect, name, False)
                except Exception:
                    continue
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        options = getattr(self.word_app, "Options", None)
        if options is not None:
            for name, value in self._saved_options.items():
                try:
                    setattr(options, name, value)
                except Exception:
                    continue
        autocorrect = getattr(self.word_app, "AutoCorrect", None)
        if autocorrect is not None:
            for name, value in self._saved_autocorrect.items():
                try:
                    setattr(autocorrect, name, value)
                except Exception:
                    continue


class TyperEngine:
    """Types or inserts text into the selected target in a background thread."""

    def __init__(
        self,
        on_log: Optional[LogCallback] = None,
        on_done: Optional[DoneCallback] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_countdown: Optional[CountdownCallback] = None,
    ) -> None:
        self.on_log = on_log
        self.on_done = on_done
        self.on_progress = on_progress
        self.on_countdown = on_countdown
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def is_typing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def type_async(self, text: str, options: TypingOptions) -> bool:
        with self._lock:
            if self.is_typing:
                self._log("Typing is already in progress. Add the text to the queue or stop first.")
                return False
            self._stop_event.clear()
            self._pause_event.set()
            self._thread = threading.Thread(
                target=self._run_typing,
                args=(text, options),
                name="ClipboardAutoTyperEngine",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        self._log("Stop requested. Pending typing has been interrupted.")

    def pause(self) -> None:
        if self.is_typing:
            self._pause_event.clear()
            self._log("Typing paused.")

    def resume(self) -> None:
        if self.is_typing:
            self._pause_event.set()
            self._log("Typing resumed.")

    def toggle_pause(self) -> None:
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    def _run_typing(self, text: str, options: TypingOptions) -> None:
        try:
            self._validate_text(text)
            cps = max(config.MIN_CPS, min(config.MAX_CPS, int(options.characters_per_second)))
            min_delay, max_delay = sanitize_random_delay(options.random_delay_min_seconds, options.random_delay_max_seconds)
            target_kind, mode = self._resolve_target_and_mode(options)

            self._log(
                f"Typing will begin after {options.initial_delay_seconds:.1f} second(s). "
                f"Target: {target_kind}. Mode: {mode}. Click inside the destination now."
            )
            if not self._wait_for_initial_delay(options.initial_delay_seconds):
                self._finish(False, "Typing stopped before it started.")
                return

            if target_kind == "word":
                self._run_word(text, mode, cps, options, min_delay, max_delay)
            elif target_kind == "browser":
                self._run_browser(text, mode, cps, options, min_delay, max_delay)
            else:
                self._finish(False, "No supported active destination was detected.")
        except Exception as exc:
            self._finish(False, f"Typing failed: {exc}")
        finally:
            if self.on_countdown:
                self.on_countdown(0)

    def _resolve_target_and_mode(self, options: TypingOptions) -> Tuple[str, str]:
        mode = options.insertion_mode if options.insertion_mode in config.INSERTION_MODES else config.DEFAULT_INSERTION_MODE
        target = options.target_mode if options.target_mode in config.TARGET_MODES else config.DEFAULT_TARGET_MODE

        if target == config.TARGET_MODE_WORD:
            if mode not in (config.INSERTION_MODE_SAFE_WORD, config.INSERTION_MODE_WORD_HUMAN):
                raise ValueError("Destination is Word, but the selected typing method is for browsers. Choose a Word method.")
            return "word", mode

        if target == config.TARGET_MODE_GOOGLE_DOCS:
            if mode not in (config.INSERTION_MODE_BROWSER_PASTE, config.INSERTION_MODE_BROWSER_HUMAN):
                raise ValueError("Destination is Google Docs/browser, but the selected typing method is for Word. Choose a Browser method.")
            return "browser", mode

        # Auto detect based on the active window first, then mode.
        if TargetDetector.is_word_active():
            if mode in (config.INSERTION_MODE_BROWSER_PASTE, config.INSERTION_MODE_BROWSER_HUMAN):
                return "browser", mode
            return "word", mode
        if TargetDetector.is_supported_browser_active():
            if mode in (config.INSERTION_MODE_SAFE_WORD, config.INSERTION_MODE_WORD_HUMAN):
                return "word", mode
            return "browser", mode

        if mode in (config.INSERTION_MODE_SAFE_WORD, config.INSERTION_MODE_WORD_HUMAN):
            return "word", mode
        return "browser", mode

    def _run_word(
        self,
        text: str,
        mode: str,
        cps: int,
        options: TypingOptions,
        min_delay: float,
        max_delay: float,
    ) -> None:
        try:
            import pythoncom
        except Exception as exc:
            self._finish(False, f"pywin32 is required for Microsoft Word automation: {exc}")
            return

        pythoncom.CoInitialize()
        try:
            if not TargetDetector.is_word_running():
                self._finish(False, "Microsoft Word is not running. Open Word and a document first.")
                return
            if options.require_active_target and not TargetDetector.is_word_active():
                self._finish(False, "Microsoft Word is not active. Click inside Word and try again.")
                return
            word_app = TargetDetector.get_active_word_application()
            selection = getattr(word_app, "Selection", None)
            if selection is None:
                self._finish(False, "No active Word selection was found. Click inside a Word document and try again.")
                return
            if mode == config.INSERTION_MODE_SAFE_WORD:
                self._safe_insert_word(selection, text)
            else:
                self._human_type_word(word_app, selection, text, cps, options, min_delay, max_delay)
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _safe_insert_word(self, selection, text: str) -> None:
        total = len(text)
        self._log(f"Safe Insert: inserting {total} character(s) directly through Word for exact Unicode preservation.")
        self._progress(0, total)
        if self._stop_event.is_set():
            self._finish(False, "Typing stopped before insertion.")
            return
        self._pause_event.wait()
        selection.Range.Text = normalize_line_breaks_for_word(text)
        try:
            selection.Collapse(0)  # Word constant wdCollapseEnd = 0.
        except Exception:
            pass
        self._progress(total, total)
        self._finish(True, f"Safe Insert completed successfully. {total} character(s) processed.")

    def _human_type_word(
        self,
        word_app,
        selection,
        text: str,
        cps: int,
        options: TypingOptions,
        min_delay: float,
        max_delay: float,
    ) -> None:
        total = len(text)
        typed = 0
        self._log(self._delay_message("Word Human Type", total, cps, options.random_delay_enabled, min_delay, max_delay))
        with AutoCorrectGuard(word_app):
            index = 0
            while index < total:
                if self._stop_event.is_set():
                    self._finish(False, f"Typing stopped after {typed} of {total} character(s).")
                    return
                self._pause_event.wait()
                if options.require_active_target and typed % config.TARGET_ACTIVE_CHECK_INTERVAL_CHARS == 0:
                    if not TargetDetector.is_word_active():
                        self._wait_until_target_returns("Word", TargetDetector.is_word_active, typed, total)
                        if self._stop_event.is_set():
                            return
                character = text[index]
                if character == "\r":
                    if index + 1 < total and text[index + 1] == "\n":
                        index += 1
                        typed += 1
                    selection.TypeParagraph()
                elif character == "\n":
                    selection.TypeParagraph()
                elif character == "\t":
                    selection.TypeText("\t")
                else:
                    selection.TypeText(character)
                typed += 1
                index += 1
                self._progress(typed, total)
                self._sleep_character_delay(cps, options.random_delay_enabled, min_delay, max_delay)
        self._finish(True, f"Word Human Type completed successfully. {typed} character(s) processed.")

    def _run_browser(
        self,
        text: str,
        mode: str,
        cps: int,
        options: TypingOptions,
        min_delay: float,
        max_delay: float,
    ) -> None:
        try:
            import pyautogui
        except Exception as exc:
            self._finish(False, f"pyautogui is required for Google Docs/browser typing: {exc}")
            return

        if options.require_active_target and not TargetDetector.is_supported_browser_active():
            self._finish(False, "A supported browser is not active. Open Google Docs and click inside the document.")
            return

        if mode == config.INSERTION_MODE_BROWSER_PASTE:
            self._browser_paste(pyautogui, text, options.restore_clipboard_after_paste)
        else:
            self._browser_human_type(pyautogui, text, cps, options, min_delay, max_delay)

    def _browser_paste(self, pyautogui, text: str, restore_clipboard: bool) -> None:
        total = len(text)
        self._log(
            "Browser Paste: pressing Ctrl+V in the active browser. If the requested text is not currently on the clipboard, "
            "the app temporarily places it there and restores the previous clipboard text afterward."
        )
        self._progress(0, total)
        if self._stop_event.is_set():
            self._finish(False, "Typing stopped before paste.")
            return
        self._pause_event.wait()

        original_text: Optional[str] = None
        changed_clipboard = False
        try:
            original_text = pyperclip.paste()
        except Exception:
            original_text = None
        try:
            if original_text != text:
                pyperclip.copy(text)
                changed_clipboard = True
                time.sleep(0.08)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.10)
        finally:
            if restore_clipboard and changed_clipboard and original_text is not None:
                try:
                    pyperclip.copy(original_text)
                    self._log("Clipboard restored after Browser Paste.")
                except Exception as exc:
                    self._log(f"WARNING: Could not restore clipboard after paste: {exc}")
        self._progress(total, total)
        self._finish(True, f"Browser Paste completed successfully. {total} character(s) processed.")

    def _browser_human_type(
        self,
        pyautogui,
        text: str,
        cps: int,
        options: TypingOptions,
        min_delay: float,
        max_delay: float,
    ) -> None:
        """Human-style browser typing with Unicode fallback.

        pyautogui can only type common keyboard characters reliably. In v4.1,
        unsupported Unicode/accent/emoji clusters are no longer treated as a
        hard error. Instead, the engine pastes only those clusters, restores the
        original clipboard at the end, and continues typing the rest character by
        character. This preserves Google Docs output while keeping the visible
        natural typing behavior for normal text.
        """
        total = len(text)
        typed = 0
        pasted_clusters = 0
        self._log(
            self._delay_message(
                "Browser Human Type hybrid Unicode",
                total,
                cps,
                options.random_delay_enabled,
                min_delay,
                max_delay,
            )
        )

        original_text: Optional[str] = None
        clipboard_changed = False
        if options.restore_clipboard_after_paste:
            try:
                original_text = pyperclip.paste()
            except Exception:
                original_text = None

        try:
            index = 0
            while index < total:
                if self._stop_event.is_set():
                    self._finish(False, f"Typing stopped after {typed} of {total} character(s).")
                    return
                self._pause_event.wait()
                if options.require_active_target and typed % config.TARGET_ACTIVE_CHECK_INTERVAL_CHARS == 0:
                    if not TargetDetector.is_supported_browser_active():
                        self._wait_until_target_returns("Browser", TargetDetector.is_supported_browser_active, typed, total)
                        if self._stop_event.is_set():
                            return

                segment, next_index, segment_kind = next_browser_human_segment(text, index)
                if segment_kind == "key":
                    character = segment
                    if character == "\r":
                        if next_index < total and text[next_index] == "\n":
                            next_index += 1
                            typed += 1
                        pyautogui.press("enter")
                    elif character == "\n":
                        pyautogui.press("enter")
                    elif character == "\t":
                        pyautogui.press("tab")
                    else:
                        pyautogui.write(character)
                else:
                    # Paste only the Unicode/accent/emoji cluster that cannot be
                    # typed by pyautogui. This is the reliable browser path for
                    # characters such as ä, ñ, emoji, keycap emoji, and combining
                    # accents.
                    if not self._paste_browser_segment(pyautogui, segment):
                        return
                    pasted_clusters += 1
                    clipboard_changed = True

                typed += len(segment)
                index = next_index
                self._progress(min(typed, total), total)
                self._sleep_character_delay(cps, options.random_delay_enabled, min_delay, max_delay)
        finally:
            if options.restore_clipboard_after_paste and clipboard_changed and original_text is not None:
                try:
                    pyperclip.copy(original_text)
                    self._log("Clipboard restored after Browser Human Type Unicode fallback.")
                except Exception as exc:
                    self._log(f"WARNING: Could not restore clipboard after Unicode fallback: {exc}")

        if pasted_clusters:
            self._finish(
                True,
                f"Browser Human Type completed with Unicode fallback. {typed} character(s) processed; "
                f"{pasted_clusters} Unicode/accent/emoji segment(s) pasted exactly.",
            )
        else:
            self._finish(True, f"Browser Human Type completed successfully. {typed} character(s) processed.")

    def _paste_browser_segment(self, pyautogui, segment: str) -> bool:
        if self._stop_event.is_set():
            self._finish(False, "Typing stopped before Unicode fallback paste.")
            return False
        self._pause_event.wait()
        try:
            pyperclip.copy(segment)
            time.sleep(0.04)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.04)
            return True
        except Exception as exc:
            self._finish(False, f"Unicode fallback paste failed: {exc}")
            return False

    def _wait_until_target_returns(self, label: str, predicate: Callable[[], bool], typed: int, total: int) -> None:
        self._log(f"{label} lost focus. Typing is paused until {label} is active again.")
        while not self._stop_event.is_set() and not predicate():
            time.sleep(0.20)
        if self._stop_event.is_set():
            self._finish(False, f"Typing stopped after {typed} of {total} character(s).")
            return
        self._log(f"{label} is active again. Typing resumed.")

    def _sleep_character_delay(self, cps: int, randomized: bool, min_delay: float, max_delay: float) -> None:
        delay = random.uniform(min_delay, max_delay) if randomized else 1.0 / max(1, cps)
        end_at = time.time() + max(0.0, delay)
        while time.time() < end_at:
            if self._stop_event.is_set():
                return
            self._pause_event.wait(timeout=0.02)
            time.sleep(min(0.02, max(0.0, end_at - time.time())))

    @staticmethod
    def _delay_message(label: str, total: int, cps: int, randomized: bool, min_delay: float, max_delay: float) -> str:
        if randomized:
            return f"{label}: typing {total} character(s) with randomized {min_delay:.3f}-{max_delay:.3f}s key delay."
        return f"{label}: typing {total} character(s) at {cps} character(s) per second."

    def _wait_for_initial_delay(self, seconds: float) -> bool:
        end_at = time.time() + max(0.0, seconds)
        while time.time() < end_at:
            if self._stop_event.is_set():
                return False
            self._pause_event.wait(timeout=0.05)
            remaining = max(0.0, end_at - time.time())
            if self.on_countdown:
                self.on_countdown(remaining)
            time.sleep(min(config.COUNTDOWN_UPDATE_SECONDS, max(0.05, remaining)))
        return True

    @staticmethod
    def _validate_text(text: str) -> None:
        if not isinstance(text, str):
            raise ValueError("Clipboard content is not text.")
        if text == "":
            raise ValueError("Clipboard is empty.")
        unsupported = []
        for character in text:
            if character in "\r\n\t":
                continue
            category = unicodedata.category(character)
            if category.startswith("C") and not is_allowed_unicode_format_control(character):
                unsupported.append(repr(character))
                if len(unsupported) >= 5:
                    break
        if unsupported:
            raise ValueError("Clipboard contains unsupported control characters: " + ", ".join(unsupported))

    def _progress(self, current: int, total: int) -> None:
        if self.on_progress:
            self.on_progress(current, total)

    def _log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)

    def _finish(self, success: bool, message: str) -> None:
        if self.on_done:
            self.on_done(success, message)
        else:
            self._log(message)


def normalize_line_breaks_for_word(text: str) -> str:
    """Convert common text newlines to Word paragraph marks."""
    text = text.replace("\r\n", "\r")
    text = text.replace("\n", "\r")
    return text


def sanitize_random_delay(min_delay: float, max_delay: float) -> Tuple[float, float]:
    try:
        minimum = float(min_delay)
    except (TypeError, ValueError):
        minimum = config.DEFAULT_RANDOM_DELAY_MIN_SECONDS
    try:
        maximum = float(max_delay)
    except (TypeError, ValueError):
        maximum = config.DEFAULT_RANDOM_DELAY_MAX_SECONDS
    minimum = max(config.MIN_RANDOM_DELAY_SECONDS, min(config.MAX_RANDOM_DELAY_SECONDS, minimum))
    maximum = max(config.MIN_RANDOM_DELAY_SECONDS, min(config.MAX_RANDOM_DELAY_SECONDS, maximum))
    if minimum > maximum:
        minimum, maximum = maximum, minimum
    return minimum, maximum


def is_browser_key_safe_character(character: str) -> bool:
    """Return True when pyautogui can type the character directly."""
    if character in "\r\n\t":
        return True
    allowed = set(string.printable) - {"\x0b", "\x0c"}
    return character in allowed


def is_unicode_joiner_or_modifier(character: str) -> bool:
    """Characters that must stay attached to the nearby Unicode cluster."""
    codepoint = ord(character)
    if character == "\u200d":  # zero-width joiner, common in emoji sequences.
        return True
    if 0xFE00 <= codepoint <= 0xFE0F:  # variation selectors.
        return True
    if 0xE0100 <= codepoint <= 0xE01EF:  # supplemental variation selectors.
        return True
    category = unicodedata.category(character)
    return category.startswith("M")


def is_allowed_unicode_format_control(character: str) -> bool:
    """Allow safe Unicode format controls needed for emoji/text clusters."""
    return is_unicode_joiner_or_modifier(character) or character in {"\u200c"}


def next_browser_human_segment(text: str, index: int) -> Tuple[str, int, str]:
    """Return the next segment and whether to type it as a key or paste it.

    Segment kind is ``key`` for common keyboard characters and ``paste`` for
    Unicode/accent/emoji clusters that cannot be typed reliably by pyautogui.
    """
    character = text[index]

    # Type plain line breaks and tabs through the keyboard path.
    if character in "\r\n\t":
        return character, index + 1, "key"

    # Plain printable ASCII can be typed directly unless it begins a combining
    # sequence such as e + combining acute accent or 1 + variation selector.
    if is_browser_key_safe_character(character):
        next_index = index + 1
        if next_index >= len(text) or not is_unicode_joiner_or_modifier(text[next_index]):
            return character, next_index, "key"

    # Unicode fallback. Capture the full cluster/run that needs exact insertion.
    start = index
    end = index + 1
    while end < len(text):
        current = text[end]
        previous = text[end - 1]
        if current in "\r\n\t":
            break
        if not is_browser_key_safe_character(current):
            end += 1
            continue
        if is_unicode_joiner_or_modifier(current) or previous == "\u200d":
            end += 1
            continue
        break
    return text[start:end], end, "paste"


def first_unsupported_browser_human_character(text: str) -> Optional[Tuple[str, int]]:
    """Backward-compatible helper: v4.1 no longer rejects these characters."""
    for index, character in enumerate(text):
        if character in "\r\n\t":
            continue
        if not is_browser_key_safe_character(character):
            return character, index
    return None
