"""Voice Input System — Main controller.

Usage:
    python -m src.main              # Continuous recognition with hotkey
    python -m src.main --once       # Single-shot recognition (no hotkey)
    python -m src.main --no-gui     # Continuous mode without GUI overlay
"""

import argparse
import logging
import sys
import threading
import time

from .config import AppConfig
from .recognizer import recognize_once, ContinuousRecognizer
from .refiner import refine_text, warmup
from .output import paste_text
from .hotkey import HotkeyListener
from . import ui

try:
    import tkinter as tk

    _HAS_TK = True
except ImportError:
    _HAS_TK = False

try:
    from .gui import VoiceOverlay
    from .audio_level import AudioLevelMonitor

    _HAS_GUI = True
except ImportError:
    _HAS_GUI = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def run_once(config: AppConfig) -> None:
    """Single-shot recognition → (optional refinement) → paste."""
    ui.show_status("マイクに向かって話してください…")
    text = recognize_once(config.speech)

    if not text:
        ui.show_result("音声を検出できませんでした。")
        return

    ui.show_result(text)

    if config.enable_refinement:
        ui.show_status("テキストを推敲中…")
        text = refine_text(text, config.openai)
        ui.show_result(f"(推敲後) {text}")

    time.sleep(0.05)
    if paste_text(text):
        ui.show_status("貼り付け完了")
    else:
        ui.show_status("貼り付け失敗（権限設定を確認してください）")


def run_continuous(config: AppConfig, use_gui: bool = True) -> None:
    """Hotkey-driven continuous recognition."""
    # GUI setup
    root: tk.Tk | None = None
    overlay: VoiceOverlay | None = None
    audio_monitor: AudioLevelMonitor | None = None

    if use_gui and _HAS_TK and _HAS_GUI:
        try:
            root = tk.Tk()
            overlay = VoiceOverlay(root)
            audio_monitor = AudioLevelMonitor()
            logger.info("GUI overlay enabled")
        except Exception:
            logger.warning("GUI initialization failed, running without overlay", exc_info=True)
            root = None
            overlay = None
            audio_monitor = None

    recognizer: ContinuousRecognizer | None = None

    def _gui(method, *args):
        """Safely dispatch a GUI call to the main thread."""
        if root is not None and overlay is not None:
            root.after(0, method, *args)

    def on_activate() -> None:
        nonlocal recognizer
        ui.show_status("録音中… もう一度ホットキーで停止")
        if overlay:
            _gui(overlay.show, "recording")
        if audio_monitor and root and overlay:
            audio_monitor.start(
                lambda level: root.after(0, overlay.update_level, level),
            )
        recognizer = ContinuousRecognizer(
            cfg=config.speech,
            on_partial=ui.show_partial,
        )
        recognizer.start()

    def on_deactivate() -> None:
        nonlocal recognizer
        if recognizer is None:
            return

        if audio_monitor:
            audio_monitor.stop()

        ui.show_status("認識を停止中…")
        if overlay:
            _gui(overlay.show, "refining")

        text = recognizer.stop()
        recognizer = None

        if not text:
            ui.show_result("音声を検出できませんでした。")
            if overlay:
                _gui(overlay.hide)
            return

        ui.show_result(text)

        if config.enable_refinement:
            ui.show_status("テキストを推敲中…")
            text = refine_text(text, config.openai)
            ui.show_result(f"(推敲後) {text}")

        # macOS CGEvent/TSM APIs require the main thread for paste.
        # Use root.after() to dispatch paste to the tkinter main thread.
        def _do_paste():
            if paste_text(text):
                ui.show_status("貼り付け完了")
            else:
                ui.show_status("貼り付け失敗（権限設定を確認してください）")
            if overlay:
                overlay.show("done")
            print()
            ui.show_status(f"待機中… [{config.hotkey}] で録音開始")

        delay_ms = int(config.output_post_hotkey_delay_sec * 1000)
        if root is not None:
            root.after(delay_ms, _do_paste)
        else:
            time.sleep(config.output_post_hotkey_delay_sec)
            _do_paste()

    listener = HotkeyListener(
        hotkey=config.hotkey,
        on_activate=on_activate,
        on_deactivate=on_deactivate,
    )

    print("=" * 50)
    print("  Voice Input System")
    print(f"  ホットキー: {config.hotkey}")
    print(f"  テキスト推敲: {'有効' if config.enable_refinement else '無効'}")
    print(f"  言語: {config.speech.language}")
    print(f"  GUI: {'有効' if overlay else '無効'}")
    print("  終了: Ctrl+C")
    print("=" * 50)
    ui.show_status(f"待機中… [{config.hotkey}] で録音開始")
    print()

    listener.start()

    if root is not None:
        # tkinter mainloop on main thread; Ctrl+C handled via protocol
        def _on_close():
            listener.stop()
            if audio_monitor:
                audio_monitor.stop()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", _on_close)
        try:
            root.mainloop()
        except KeyboardInterrupt:
            _on_close()
    else:
        # No GUI — block on listener like before
        try:
            listener.wait()
        except KeyboardInterrupt:
            print("\n終了します。")
        finally:
            listener.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice Input System")
    parser.add_argument("--once", action="store_true", help="Single-shot mode (no hotkey)")
    parser.add_argument("--no-gui", action="store_true", help="Disable GUI overlay")
    args = parser.parse_args()

    config = AppConfig()
    errors = config.validate()
    if errors:
        for e in errors:
            logger.error(e)
        print("\n環境変数を設定してください。.env.example を参照してください。")
        sys.exit(1)

    # Pre-establish HTTP connection to reduce first-call latency.
    if config.enable_refinement:
        warmup(config.openai)

    if args.once:
        run_once(config)
    else:
        run_continuous(config, use_gui=not args.no_gui)


if __name__ == "__main__":
    main()
