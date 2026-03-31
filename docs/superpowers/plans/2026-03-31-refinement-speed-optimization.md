# 推敲応答速度最適化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 音声認識後の推敲パイプライン遅延を1.5秒から0.6-0.8秒に短縮する

**Architecture:** 現行の一括LLM推敲アーキテクチャを維持しつつ、不要なウィンドウ管理処理の除去（-300〜500ms）、STT側ポストプロセス有効化、システムプロンプト最適化、ポストホットキー遅延短縮（-150ms）で高速化する。

**Tech Stack:** Python, Azure Speech SDK, OpenAI Python SDK, pyautogui, pynput

---

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/output.py` | Modify | `get_frontmost_app`, `_activate_app` 削除、`paste_text` から `target_app` 除去 |
| `src/main.py` | Modify | ウィンドウ管理コード除去、import整理 |
| `src/recognizer.py` | Modify | STT TrueText/dictation 有効化 |
| `src/refiner.py` | Modify | システムプロンプト最適化（フィラー除去指示追加） |
| `.env` | Modify | `OUTPUT_POST_HOTKEY_DELAY_SEC` を `0.1` に変更 |

---

### Task 1: ウィンドウ再アクティベーション除去 — output.py

**Files:**
- Modify: `src/output.py:28-92` (関数削除), `src/output.py:159-224` (paste_text簡略化)

- [ ] **Step 1: output.py から get_frontmost_app と _activate_app を削除**

`src/output.py` から以下を削除:
- `get_frontmost_app()` 関数（行28-58）
- `_activate_app()` 関数（行61-92）
- `subprocess` import（他で使っている `_send_paste_hotkey_with_osascript` があるので残す）

- [ ] **Step 2: paste_text から target_app を除去**

`src/output.py` の `paste_text` 関数を以下に変更:

```python
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
```

- [ ] **Step 3: 動作確認**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -c "from src.output import paste_text; print('import ok')"`
Expected: `import ok`

---

### Task 2: ウィンドウ管理除去 — main.py

**Files:**
- Modify: `src/main.py:15` (import), `src/main.py:51-96` (run_continuous)

- [ ] **Step 1: main.py のimportと変数を更新**

`src/main.py` を以下のように変更:

import行を変更:
```python
# Before:
from .output import paste_text, get_frontmost_app
# After:
from .output import paste_text
```

`run_continuous` 関数の `on_activate` を変更:
```python
    def on_activate() -> None:
        nonlocal recognizer
        ui.show_status("録音中… もう一度ホットキーで停止")
        recognizer = ContinuousRecognizer(
            cfg=config.speech,
            on_partial=ui.show_partial,
        )
        recognizer.start()
```

`run_continuous` 関数の冒頭の変数宣言を変更:
```python
    recognizer: ContinuousRecognizer | None = None
    # frontmost_app 変数を削除
```

`on_deactivate` の paste_text 呼び出しを変更:
```python
        # Before:
        if paste_text(text, target_app=frontmost_app):
        # After:
        if paste_text(text):
```

- [ ] **Step 2: 動作確認**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -c "from src.main import main; print('import ok')"`
Expected: `import ok`

---

### Task 3: Azure STT TrueText 有効化

**Files:**
- Modify: `src/recognizer.py:18-24` (_create_speech_config)

- [ ] **Step 1: _create_speech_config に dictation モードを追加**

`src/recognizer.py` の `_create_speech_config` を以下に変更:

```python
def _create_speech_config(cfg: AzureSpeechConfig) -> speechsdk.SpeechConfig:
    speech_config = speechsdk.SpeechConfig(
        subscription=cfg.subscription_key,
        region=cfg.region,
    )
    speech_config.speech_recognition_language = cfg.language
    # Enable dictation mode for better punctuation and formatting.
    speech_config.enable_dictation()
    return speech_config
```

- [ ] **Step 2: 動作確認**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -c "from src.recognizer import _create_speech_config; print('import ok')"`
Expected: `import ok`

---

### Task 4: システムプロンプト最適化

**Files:**
- Modify: `src/refiner.py:15-19` (SYSTEM_PROMPT)

- [ ] **Step 1: SYSTEM_PROMPT を短縮しフィラー除去指示を追加**

`src/refiner.py` の `SYSTEM_PROMPT` を以下に変更:

```python
SYSTEM_PROMPT = (
    "音声テキストを整形。言い淀み除去、誤字修正、句読点補正。"
    "意味を変えず整形後テキストのみ返す。"
)
```

変更理由:
- 98文字 → 42文字に短縮（入力トークン削減）
- 「言い淀み除去」を明示的に追加
- 冗長な敬語表現を除去

- [ ] **Step 2: 動作確認**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -c "from src.refiner import SYSTEM_PROMPT; print(f'prompt: {len(SYSTEM_PROMPT)} chars'); print(SYSTEM_PROMPT)"`
Expected: 42文字程度のプロンプトが表示される

---

### Task 5: ポストホットキー遅延短縮

**Files:**
- Modify: `.env`

- [ ] **Step 1: OUTPUT_POST_HOTKEY_DELAY_SEC を 0.1 に変更**

`.env` ファイルの以下の行を変更:

```
# Before:
OUTPUT_POST_HOTKEY_DELAY_SEC=0.25
# After:
OUTPUT_POST_HOTKEY_DELAY_SEC=0.1
```

---

### Task 6: 統合動作確認

- [ ] **Step 1: 全モジュールのインポートテスト**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -c "from src.main import main; from src.output import paste_text; from src.refiner import SYSTEM_PROMPT, refine_text; from src.recognizer import ContinuousRecognizer; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 2: 実行テスト（手動）**

Run: `cd /Users/makoto/Downloads/voice-input-system && python -m src.main`

確認項目:
- ホットキーで録音開始/停止が動作する
- 推敲後のログに `Text refined in XXX ms` が表示される
- 推敲時間が以前（~1000ms）より短縮されている
- テキストが正しくペーストされる
