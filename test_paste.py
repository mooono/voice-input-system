"""Paste debugging script.

Usage:
    python test_paste.py

5秒後にテスト文字列をペーストします。
その間に貼り付け先アプリ（テキストエディタ等）をクリックしてください。
"""

import subprocess
import time
import pyperclip
from pynput.keyboard import Controller, Key
import pyautogui

TEST_TEXT = "Hello, this is a paste test! こんにちは"


def test_osascript():
    print("\n--- Method 1: osascript ---")
    pyperclip.copy(TEST_TEXT)
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "v" using command down'],
            capture_output=True, text=True,
        )
        print(f"  exit code: {r.returncode}")
        if r.stderr:
            print(f"  stderr: {r.stderr.strip()}")
        if r.returncode == 0:
            print("  ✅ Success")
        else:
            print("  ❌ Failed")
    except Exception as e:
        print(f"  ❌ Exception: {e}")


def test_pynput():
    print("\n--- Method 2: pynput ---")
    pyperclip.copy(TEST_TEXT)
    try:
        kb = Controller()
        with kb.pressed(Key.cmd):
            kb.tap("v")
        print("  ✅ No exception (check if text appeared)")
    except Exception as e:
        print(f"  ❌ Exception: {e}")


def test_pyautogui():
    print("\n--- Method 3: pyautogui ---")
    pyperclip.copy(TEST_TEXT)
    try:
        pyautogui.hotkey("command", "v")
        print("  ✅ No exception (check if text appeared)")
    except Exception as e:
        print(f"  ❌ Exception: {e}")


def test_direct_type():
    print("\n--- Method 4: pynput direct type ---")
    try:
        kb = Controller()
        kb.type(TEST_TEXT)
        print("  ✅ No exception (check if text appeared)")
    except Exception as e:
        print(f"  ❌ Exception: {e}")


print("5秒後にペーストを試みます。貼り付け先アプリをクリックしてください。")
for i in range(5, 0, -1):
    print(f"  {i}...")
    time.sleep(1)

test_osascript()
time.sleep(1)
test_pynput()
time.sleep(1)
test_pyautogui()
time.sleep(1)
test_direct_type()
