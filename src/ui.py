"""Console-based UI module.

Provides simple text-based feedback and confirmation.
"""

import sys
import logging

logger = logging.getLogger(__name__)


def show_status(message: str) -> None:
    sys.stdout.write(f"\r\033[K[状態] {message}")
    sys.stdout.flush()


def show_partial(text: str) -> None:
    sys.stdout.write(f"\r\033[K[認識中] {text}")
    sys.stdout.flush()


def show_result(text: str) -> None:
    print(f"\n[結果] {text}")


def confirm_paste(text: str) -> bool:
    """Ask user to confirm before pasting. Returns True to paste."""
    print(f"\n{'='*50}")
    print(f"[確認] 以下のテキストを貼り付けますか？")
    print(f"  {text}")
    print(f"{'='*50}")
    choice = input("[Y/n] > ").strip().lower()
    return choice in ("", "y", "yes")
