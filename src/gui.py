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


def _get_overlay_position(root: tk.Tk, width: int) -> tuple[int, int]:
    """Get overlay position centered at top of the screen with mouse cursor."""
    if _SYSTEM == "Darwin":
        try:
            from AppKit import NSEvent, NSScreen

            mouse = NSEvent.mouseLocation()
            primary_h = NSScreen.screens()[0].frame().size.height

            for screen in NSScreen.screens():
                f = screen.frame()
                if (f.origin.x <= mouse.x < f.origin.x + f.size.width
                        and f.origin.y <= mouse.y < f.origin.y + f.size.height):
                    # Convert AppKit coords (origin bottom-left) to tkinter (top-left)
                    screen_top_tk = int(primary_h - (f.origin.y + f.size.height))
                    center_x = int(f.origin.x + (f.size.width - width) / 2)
                    # 40px below screen top (below menu bar)
                    return center_x, screen_top_tk + 40
        except Exception:
            logger.debug("NSScreen lookup failed, using fallback", exc_info=True)

    # Fallback: center on primary screen
    sw = root.winfo_screenwidth()
    return (sw - width) // 2, 40


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
            try:
                from AppKit import NSApp
                NSApp.setActivationPolicy_(1)  # Accessory: no dock, no focus steal
            except Exception:
                pass

        # Use alpha for show/hide to avoid withdraw/deiconify focus stealing
        root.attributes("-alpha", 0.0)

        # Place offscreen initially
        root.geometry(f"{_WIDTH}x{_HEIGHT}+0+-{_HEIGHT}")

        # Canvas
        self._canvas = tk.Canvas(
            root,
            width=_WIDTH,
            height=_HEIGHT,
            bg=_BG,
            highlightthickness=0,
        )
        self._canvas.pack()

        # Elements
        self._dot = self._canvas.create_oval(
            _DOT_X,
            _DOT_Y,
            _DOT_X + _DOT_SIZE,
            _DOT_Y + _DOT_SIZE,
            fill=_RED,
            outline="",
        )
        self._bar_bg = self._canvas.create_rectangle(
            _BAR_X1, _BAR_Y1, _BAR_X2, _BAR_Y2, fill=_BAR_BG, outline="",
        )
        self._bar_fg = self._canvas.create_rectangle(
            _BAR_X1, _BAR_Y1, _BAR_X1, _BAR_Y2, fill=_RED, outline="",
        )
        self._label = self._canvas.create_text(
            _TEXT_X,
            _HEIGHT // 2,
            text="",
            fill=_TEXT_COLOR,
            font=("Segoe UI" if _SYSTEM == "Windows" else "Helvetica", 11),
            anchor="w",
        )

    # -- Public API --

    def show(self, state: str) -> None:
        """Change state and show overlay. state: recording|refining|done"""
        self._cancel_timer()
        self._state = state

        if state == "recording":
            # Reposition to current mouse screen each time recording starts
            x, y = _get_overlay_position(self._root, _WIDTH)
            self._root.geometry(f"{_WIDTH}x{_HEIGHT}+{x}+{y}")

            self._rec_start = time.monotonic()
            self._canvas.itemconfig(self._dot, fill=_RED)
            self._canvas.itemconfig(self._bar_fg, fill=_RED)
            self._canvas.coords(
                self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1, _BAR_Y2,
            )
            self._canvas.itemconfig(self._label, text="0:00")
            self._root.attributes("-alpha", 0.9)
            self._tick_timer()

        elif state == "refining":
            self._prog_start = time.monotonic()
            self._canvas.itemconfig(self._dot, fill=_YELLOW)
            self._canvas.itemconfig(self._bar_fg, fill=_YELLOW)
            self._canvas.coords(
                self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1, _BAR_Y2,
            )
            self._canvas.itemconfig(self._label, text="")
            self._tick_progress()

        elif state == "done":
            self._canvas.itemconfig(self._dot, fill=_GREEN)
            self._canvas.itemconfig(self._bar_fg, fill=_GREEN)
            self._canvas.coords(
                self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X2, _BAR_Y2,
            )
            self._canvas.itemconfig(self._label, text="✓")
            self._timer_id = self._root.after(_DONE_DISPLAY_MS, self.hide)

    def update_level(self, level: float) -> None:
        """Update audio level bar. level: 0.0-1.0. Only in recording state."""
        if self._state != "recording":
            return
        w = int(_BAR_MAX_W * max(0.0, min(level, 1.0)))
        self._canvas.coords(
            self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1 + w, _BAR_Y2,
        )

    def hide(self) -> None:
        """Hide overlay."""
        self._cancel_timer()
        self._state = "hidden"
        self._root.attributes("-alpha", 0.0)

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
        self._canvas.coords(
            self._bar_fg, _BAR_X1, _BAR_Y1, _BAR_X1 + w, _BAR_Y2,
        )
        if progress < 1.0:
            self._timer_id = self._root.after(
                _ANIM_INTERVAL_MS, self._tick_progress,
            )
