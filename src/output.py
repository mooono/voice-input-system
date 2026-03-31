"""Text output / paste module.

Inserts text into the active window using pyperclip + pyautogui.
Cross-platform support: macOS, Windows, Linux.
"""

import logging
import os
import platform
import subprocess
import time

import pyperclip
import pyautogui
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()

# Modifier keys that may interfere with Cmd+V / Ctrl+V paste.
_MODIFIER_KEYS = [Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                  Key.shift, Key.shift_l, Key.shift_r,
                  Key.alt, Key.alt_l, Key.alt_r,
                  Key.cmd, Key.cmd_l, Key.cmd_r]


def _release_all_modifiers() -> None:
    """Release all modifier keys to avoid hotkey state leaking into paste."""
    kb = Controller()
    for k in _MODIFIER_KEYS:
        try:
            kb.release(k)
        except Exception:
            pass


def _send_paste_hotkey_with_pyautogui() -> None:
    """Cross-platform paste — primary method."""
    if _SYSTEM == "Darwin":
        pyautogui.hotkey("command", "v")
    else:
        pyautogui.hotkey("ctrl", "v")


def _send_paste_hotkey_with_pynput() -> None:
    """Cross-platform paste — fallback."""
    kb = Controller()
    if _SYSTEM == "Darwin":
        with kb.pressed(Key.cmd):
            kb.tap("v")
    else:
        with kb.pressed(Key.ctrl):
            kb.tap("v")


def _send_paste_hotkey_with_osascript() -> None:
    """macOS-only paste via AppleScript."""
    if _SYSTEM != "Darwin":
        return
    subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _type_text_directly(text: str) -> None:
    kb = Controller()
    kb.type(text)


def _verify_clipboard_consumed(original_text: str, timeout: float = 0.5) -> bool:
    """Heuristic check: see if the clipboard still holds our text.

    Some apps clear/modify clipboard on paste; if unchanged we cannot
    tell for sure, so this is a best-effort signal only.
    """
    time.sleep(timeout)
    try:
        current = pyperclip.paste()
        return current == original_text  # still there → inconclusive
    except Exception:
        return True


def paste_text(text: str) -> bool:
    """Copy text to clipboard and paste it into the active window.

    Uses pyautogui as the primary method for maximum cross-platform
    compatibility (macOS / Windows / Linux), with pynput and osascript
    as fallbacks.

    Returns True when an output action was attempted successfully.
    """
    if not text:
        logger.warning("Empty text — nothing to paste")
        return False

    # Mode: paste (default) or type
    mode = os.environ.get("OUTPUT_INSERT_MODE", "paste").strip().lower()

    if mode == "type":
        try:
            _type_text_directly(text)
            logger.info("Typed %d chars into active window", len(text))
            return True
        except Exception:
            logger.exception("Direct typing failed")
            return False

    pyperclip.copy(text)

    # Release any modifier keys left over from the global hotkey.
    _release_all_modifiers()
    time.sleep(0.15)

    # Cross-platform method order: pyautogui first (most universal),
    # then pynput, then osascript (macOS-specific fallback).
    methods: list = [
        _send_paste_hotkey_with_pyautogui,
        _send_paste_hotkey_with_pynput,
    ]
    if _SYSTEM == "Darwin":
        methods.append(_send_paste_hotkey_with_osascript)

    for method in methods:
        try:
            method()
            logger.info("Pasted %d chars (method=%s)", len(text), method.__name__)
            return True
        except Exception:
            logger.exception("Paste method failed: %s", method.__name__)

    # Final fallback: type text directly to avoid silent no-op.
    try:
        _type_text_directly(text)
        logger.warning("Paste failed; typed %d chars directly as fallback", len(text))
        return True
    except Exception:
        logger.exception("All paste/typing methods failed")
        return False
