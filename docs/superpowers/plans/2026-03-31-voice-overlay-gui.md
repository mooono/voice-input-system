# Voice Overlay GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Typeless-style minimal overlay window that visualizes recording state (real-time audio level) and refinement progress (1.5s fixed progress bar).

**Architecture:** tkinter overlay on main thread, hotkey/STT/refinement on worker threads, sounddevice for audio level capture. Communication via `root.after()`.

**Tech Stack:** tkinter, sounddevice, numpy

---

### Task 1: Add sounddevice dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add sounddevice to requirements.txt**

Add `sounddevice>=0.4.6` after the existing entries.

- [ ] **Step 2: Install dependencies**

Run: `cd /Users/makoto/Downloads/voice-input-system && pip install sounddevice`

---

### Task 2: Create AudioLevelMonitor

**Files:**
- Create: `src/audio_level.py`
- Create: `tests/test_audio_level.py`

- [ ] **Step 1: Create src/audio_level.py**

```python
"""Audio level monitoring via sounddevice for GUI visualization."""

import logging
from typing import Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioLevelMonitor:
    """Capture microphone PCM data and compute RMS level for visualization."""

    def __init__(self, device: int | None = None, block_duration_ms: int = 30):
        self._device = device
        self._blocksize = int(16000 * block_duration_ms / 1000)
        self._stream: sd.InputStream | None = None
        self._callback: Callable[[float], None] | None = None

    def start(self, callback: Callable[[float], None]) -> None:
        """Start audio stream. callback receives RMS level 0.0-1.0."""
        self._callback = callback
        try:
            self._stream = sd.InputStream(
                device=self._device,
                channels=1,
                samplerate=16000,
                blocksize=self._blocksize,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info("Audio level monitor started")
        except Exception:
            logger.warning("Failed to start audio level monitor", exc_info=True)
            self._stream = None

    def stop(self) -> None:
        """Stop audio stream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            logger.info("Audio level monitor stopped")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            logger.debug("Audio status: %s", status)
        rms = float(np.sqrt(np.mean(indata ** 2)))
        level = min(rms / 0.1, 1.0)
        if self._callback:
            self._callback(level)
```

- [ ] **Step 2: Create tests/test_audio_level.py**

```python
"""Tests for AudioLevelMonitor."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from src.audio_level import AudioLevelMonitor


class TestAudioLevelMonitor:
    def test_init_defaults(self):
        monitor = AudioLevelMonitor()
        assert monitor._device is None
        assert monitor._stream is None
        assert monitor._callback is None

    def test_rms_calculation(self):
        """Verify the audio callback computes correct RMS level."""
        monitor = AudioLevelMonitor()
        levels = []
        monitor._callback = lambda level: levels.append(level)

        # Simulate audio data: sine wave with known amplitude
        amplitude = 0.05
        samples = np.full((480, 1), amplitude, dtype=np.float32)
        monitor._audio_callback(samples, 480, None, None)

        assert len(levels) == 1
        expected_rms = amplitude
        expected_level = min(expected_rms / 0.1, 1.0)
        assert abs(levels[0] - expected_level) < 0.01

    def test_rms_clamp_to_one(self):
        """Level should be clamped to 1.0 for loud audio."""
        monitor = AudioLevelMonitor()
        levels = []
        monitor._callback = lambda level: levels.append(level)

        loud_samples = np.full((480, 1), 0.5, dtype=np.float32)
        monitor._audio_callback(loud_samples, 480, None, None)

        assert levels[0] == 1.0

    def test_silence_gives_zero(self):
        """Silent audio should give level ~0.0."""
        monitor = AudioLevelMonitor()
        levels = []
        monitor._callback = lambda level: levels.append(level)

        silent = np.zeros((480, 1), dtype=np.float32)
        monitor._audio_callback(silent, 480, None, None)

        assert levels[0] == 0.0

    @patch("src.audio_level.sd.InputStream")
    def test_start_creates_stream(self, mock_cls):
        monitor = AudioLevelMonitor()
        cb = lambda level: None
        monitor.start(cb)
        mock_cls.assert_called_once()
        mock_cls.return_value.start.assert_called_once()

    @patch("src.audio_level.sd.InputStream")
    def test_stop_closes_stream(self, mock_cls):
        monitor = AudioLevelMonitor()
        monitor.start(lambda l: None)
        monitor.stop()
        mock_cls.return_value.stop.assert_called_once()
        mock_cls.return_value.close.assert_called_once()
        assert monitor._stream is None

    @patch("src.audio_level.sd.InputStream", side_effect=OSError("No device"))
    def test_start_handles_device_error(self, mock_cls):
        monitor = AudioLevelMonitor()
        monitor.start(lambda l: None)  # Should not raise
        assert monitor._stream is None
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -m pytest tests/test_audio_level.py -v`
Expected: All 7 tests PASS

---

### Task 3: Create VoiceOverlay

**Files:**
- Create: `src/gui.py`
- Create: `tests/test_gui.py`

- [ ] **Step 1: Create src/gui.py**

```python
"""Minimal overlay GUI for voice input state visualization."""

import logging
import platform
import time
import tkinter as tk

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()

# Colors
_BG = "#1a1a2e"
_RED = "#e74c3c"
_YELLOW = "#f1c40f"
_GREEN = "#2ecc71"
_BAR_BG = "#2d2d44"
_TEXT_COLOR = "#ffffff"

# Layout
_WIDTH = 320
_HEIGHT = 40
_DOT_X, _DOT_Y = 10, 12
_DOT_SIZE = 14
_BAR_X1, _BAR_Y1 = 34, 14
_BAR_X2, _BAR_Y2 = 260, 26
_BAR_MAX_W = _BAR_X2 - _BAR_X1  # 226
_TEXT_X = 275

# Timing
_PROGRESS_DURATION_MS = 1500
_DONE_DISPLAY_MS = 1000
_ANIM_INTERVAL_MS = 16  # ~60fps


class VoiceOverlay:
    """Minimal always-on-top overlay showing recording/refining state."""

    def __init__(self, root: tk.Tk):
        self._root = root
        self._state = "hidden"
        self._rec_start: float = 0.0
        self._prog_start: float = 0.0
        self._timer_id: str | None = None

        # Window setup
        root.title("Voice Input")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        if _SYSTEM == "Darwin":
            root.attributes("-alpha", 0.9)
        root.withdraw()

        # Center at top of screen
        screen_w = root.winfo_screenwidth()
        x = (screen_w - _WIDTH) // 2
        root.geometry(f"{_WIDTH}x{_HEIGHT}+{x}+40")

        # Canvas
        self._canvas = tk.Canvas(
            root, width=_WIDTH, height=_HEIGHT,
            bg=_BG, highlightthickness=0,
        )
        self._canvas.pack()

        # Elements
        self._dot = self._canvas.create_oval(
            _DOT_X, _DOT_Y, _DOT_X + _DOT_SIZE, _DOT_Y + _DOT_SIZE,
            fill=_RED, outline="",
        )
        self._bar_bg = self._canvas.create_rectangle(
            _BAR_X1, _BAR_Y1, _BAR_X2, _BAR_Y2, fill=_BAR_BG, outline="",
        )
        self._bar_fg = self._canvas.create_rectangle(
            _BAR_X1, _BAR_Y1, _BAR_X1, _BAR_Y2, fill=_RED, outline="",
        )
        self._label = self._canvas.create_text(
            _TEXT_X, _HEIGHT // 2, text="", fill=_TEXT_COLOR,
            font=("Helvetica", 11), anchor="w",
        )

    # -- Public API --

    def show(self, state: str) -> None:
        """Change state and show overlay. state: recording|refining|done"""
        self._cancel_timer()
        self._state = state

        if state == "recording":
            self._rec_start = time.monotonic()
            self._canvas.itemconfig(self._dot, fill=_RED)
            self._canvas.itemconfig(self._bar_fg, fill=_RED)
            self._canvas.coords(self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1, _BAR_Y2)
            self._canvas.itemconfig(self._label, text="0:00")
            self._root.deiconify()
            self._tick_timer()

        elif state == "refining":
            self._prog_start = time.monotonic()
            self._canvas.itemconfig(self._dot, fill=_YELLOW)
            self._canvas.itemconfig(self._bar_fg, fill=_YELLOW)
            self._canvas.coords(self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1, _BAR_Y2)
            self._canvas.itemconfig(self._label, text="")
            self._tick_progress()

        elif state == "done":
            self._canvas.itemconfig(self._dot, fill=_GREEN)
            self._canvas.itemconfig(self._bar_fg, fill=_GREEN)
            self._canvas.coords(self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X2, _BAR_Y2)
            self._canvas.itemconfig(self._label, text="✓")
            self._timer_id = self._root.after(_DONE_DISPLAY_MS, self.hide)

    def update_level(self, level: float) -> None:
        """Update audio level bar. level: 0.0-1.0. Only active in recording state."""
        if self._state != "recording":
            return
        w = int(_BAR_MAX_W * max(0.0, min(level, 1.0)))
        self._canvas.coords(self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1 + w, _BAR_Y2)

    def hide(self) -> None:
        """Hide overlay."""
        self._cancel_timer()
        self._state = "hidden"
        self._root.withdraw()

    # -- Private --

    def _cancel_timer(self) -> None:
        if self._timer_id is not None:
            self._root.after_cancel(self._timer_id)
            self._timer_id = None

    def _tick_timer(self) -> None:
        if self._state != "recording":
            return
        elapsed = int(time.monotonic() - self._rec_start)
        m, s = divmod(elapsed, 60)
        self._canvas.itemconfig(self._label, text=f"{m}:{s:02d}")
        self._timer_id = self._root.after(500, self._tick_timer)

    def _tick_progress(self) -> None:
        if self._state != "refining":
            return
        elapsed_ms = (time.monotonic() - self._prog_start) * 1000
        progress = min(elapsed_ms / _PROGRESS_DURATION_MS, 1.0)
        w = int(_BAR_MAX_W * progress)
        self._canvas.coords(self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1 + w, _BAR_Y2)
        if progress < 1.0:
            self._timer_id = self._root.after(_ANIM_INTERVAL_MS, self._tick_progress)
```

- [ ] **Step 2: Create tests/test_gui.py**

```python
"""Tests for VoiceOverlay (headless-safe using mock tk)."""

import time
import pytest
from unittest.mock import MagicMock, patch, call


class TestVoiceOverlay:
    @pytest.fixture
    def overlay(self):
        """Create a VoiceOverlay with a mocked Tk root."""
        with patch("src.gui.tk.Tk") as MockTk:
            mock_root = MockTk.return_value
            mock_root.winfo_screenwidth.return_value = 1920
            mock_canvas = MagicMock()
            mock_canvas.create_oval.return_value = 1
            mock_canvas.create_rectangle.side_effect = [2, 3]
            mock_canvas.create_text.return_value = 4
            with patch("src.gui.tk.Canvas", return_value=mock_canvas):
                from src.gui import VoiceOverlay
                ov = VoiceOverlay(mock_root)
                ov._canvas = mock_canvas
                yield ov, mock_root, mock_canvas

    def test_initial_state_hidden(self, overlay):
        ov, root, canvas = overlay
        assert ov._state == "hidden"
        root.withdraw.assert_called()

    def test_show_recording(self, overlay):
        ov, root, canvas = overlay
        ov.show("recording")
        assert ov._state == "recording"
        root.deiconify.assert_called()

    def test_show_refining(self, overlay):
        ov, root, canvas = overlay
        ov.show("refining")
        assert ov._state == "refining"

    def test_show_done(self, overlay):
        ov, root, canvas = overlay
        ov.show("done")
        assert ov._state == "done"
        root.after.assert_called()

    def test_hide(self, overlay):
        ov, root, canvas = overlay
        ov.show("recording")
        ov.hide()
        assert ov._state == "hidden"
        root.withdraw.assert_called()

    def test_update_level_during_recording(self, overlay):
        ov, root, canvas = overlay
        ov._state = "recording"
        ov.update_level(0.5)
        canvas.coords.assert_called()

    def test_update_level_ignored_when_not_recording(self, overlay):
        ov, root, canvas = overlay
        ov._state = "refining"
        canvas.coords.reset_mock()
        ov.update_level(0.5)
        canvas.coords.assert_not_called()

    def test_update_level_clamp(self, overlay):
        ov, root, canvas = overlay
        ov._state = "recording"
        ov.update_level(1.5)  # should clamp to 1.0
        ov.update_level(-0.5)  # should clamp to 0.0
        # No exception expected
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -m pytest tests/test_gui.py -v`
Expected: All 8 tests PASS

---

### Task 4: Integrate GUI into main.py

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Modify src/main.py**

Replace `run_continuous` to use tkinter mainloop on main thread, move hotkey + STT + refinement to worker threads, wire up VoiceOverlay and AudioLevelMonitor.

Key changes:
1. Import `tkinter`, `threading`, `gui.VoiceOverlay`, `audio_level.AudioLevelMonitor`
2. In `run_continuous`: create `tk.Tk()`, `VoiceOverlay`, `AudioLevelMonitor`
3. `on_activate`: start audio monitor + recognizer, dispatch GUI update via `root.after`
4. `on_deactivate`: stop audio monitor + recognizer, refine, paste, dispatch GUI update
5. Start `HotkeyListener` (already spawns pynput as daemon thread)
6. Run `root.mainloop()` instead of `listener.wait()`
7. Add `--no-gui` flag for headless environments
8. Wrap tkinter import in try/except for graceful fallback

- [ ] **Step 2: Run full system test**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -m pytest tests/ -v`
Expected: All tests PASS

---
