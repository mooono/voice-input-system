"""Global hotkey listener module using pynput."""

import logging
import threading
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)

# Map config key names → pynput Key objects
_SPECIAL_KEYS = {
    "ctrl": keyboard.Key.ctrl,
    "ctrl_l": keyboard.Key.ctrl_l,
    "ctrl_r": keyboard.Key.ctrl_r,
    "shift": keyboard.Key.shift,
    "shift_l": keyboard.Key.shift_l,
    "shift_r": keyboard.Key.shift_r,
    "alt": keyboard.Key.alt,
    "alt_l": keyboard.Key.alt_l,
    "alt_r": keyboard.Key.alt_r,
    "cmd": keyboard.Key.cmd,
    "command": keyboard.Key.cmd,
    "space": keyboard.Key.space,
    "tab": keyboard.Key.tab,
    "enter": keyboard.Key.enter,
    "esc": keyboard.Key.esc,
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
}


def _parse_hotkey(hotkey_str: str) -> set:
    """Parse 'ctrl+shift+space' into a set of pynput key objects."""
    keys = set()
    for part in hotkey_str.lower().split("+"):
        part = part.strip()
        if part in _SPECIAL_KEYS:
            keys.add(_SPECIAL_KEYS[part])
        elif len(part) == 1:
            keys.add(keyboard.KeyCode.from_char(part))
        else:
            logger.warning("Unknown key: %s", part)
    return keys


class HotkeyListener:
    """Register a global hotkey and invoke callbacks on press/release."""

    def __init__(
        self,
        hotkey: str,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None] | None = None,
    ):
        self._hotkey_str = hotkey
        self._target_keys = _parse_hotkey(hotkey)
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate
        self._active = False
        self._pressed: set = set()
        self._listener: keyboard.Listener | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        logger.info("Hotkey registered: %s", self._hotkey_str)

    def wait(self) -> None:
        self._stop_event.wait()

    def stop(self) -> None:
        self._stop_event.set()
        if self._listener:
            self._listener.stop()
        logger.info("Hotkey listener stopped")

    def _normalise(self, key) -> keyboard.Key | keyboard.KeyCode | None:
        """Normalise left/right modifier variants to generic ones."""
        if isinstance(key, keyboard.Key):
            name = key.name
            if name.startswith("ctrl"):
                return keyboard.Key.ctrl
            if name.startswith("shift"):
                return keyboard.Key.shift
            if name.startswith("alt"):
                return keyboard.Key.alt
            if name.startswith("cmd"):
                return keyboard.Key.cmd
            return key
        if isinstance(key, keyboard.KeyCode):
            return key
        return None

    def _on_press(self, key) -> None:
        norm = self._normalise(key)
        if norm is not None:
            self._pressed.add(norm)
        if self._target_keys.issubset(self._pressed):
            self._pressed.clear()  # prevent repeat
            self._toggle()

    def _on_release(self, key) -> None:
        norm = self._normalise(key)
        self._pressed.discard(norm)

    def _toggle(self) -> None:
        if not self._active:
            self._active = True
            logger.info("Hotkey activated")
            self._on_activate()
        else:
            self._active = False
            logger.info("Hotkey deactivated")
            if self._on_deactivate:
                # Run on a separate thread so the listener can continue
                # processing key-release events while the callback runs.
                threading.Thread(
                    target=self._on_deactivate, daemon=True
                ).start()
