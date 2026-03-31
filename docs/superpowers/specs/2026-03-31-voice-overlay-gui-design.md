# Voice Overlay GUI Design Spec

## 概要

Typelessライクなミニマルオーバーレイウィンドウで、音声入力の状態（録音中のリアルタイムサウンドレベル、推敲中のプログレスバー）を可視化する。

## 技術選定

- **GUI**: tkinter（標準ライブラリ、追加依存なし）
- **オーディオレベル取得**: sounddevice（新規依存）
- **ウィンドウ**: ボーダーレス、常に最前面、半透明ダーク背景
- **サイズ**: 約320×40px
- **位置**: 画面上部中央

## 状態遷移

```
[非表示] ─── ホットキー押下 ───→ [録音中]
                                    │ 赤ドット + サウンドレベルバー + 経過時間
                                    │
                              ホットキー再押下
                                    │
                                    ▼
                               [推敲中]
                                    │ 黄ドット + 1.5秒固定プログレスバー（左→右）
                                    │
                              推敲完了 or ペースト完了
                                    │
                                    ▼
                               [完了]
                                    │ 緑チェック + "完了"
                                    │ 1秒後に自動消去
                                    │
                                    ▼
                               [非表示]
```

### 各状態の詳細

| 状態 | インジケータ | コンテンツ | 持続時間 |
|------|------------|-----------|---------|
| 非表示 | — | ウィンドウ非表示 | ホットキーまで |
| 録音中 | 赤ドット (●) | サウンドレベルバー + 経過時間 | ホットキー再押下まで |
| 推敲中 | 黄ドット (●) | 1.5秒固定プログレスバー（左→右） | 推敲完了まで |
| 完了 | 緑チェック (✓) | "完了" テキスト | 1秒固定 |

### 推敲無効時のフロー

`ENABLE_REFINEMENT=false`の場合、録音中→完了に直接遷移（推敲中をスキップ）。

## アーキテクチャ

### ファイル構成

```
src/
├── gui.py           # VoiceOverlay クラス（新規）
├── audio_level.py   # AudioLevelMonitor クラス（新規）
├── main.py          # メインコントローラ（変更）
├── ui.py            # コンソールUI（変更なし、共存）
└── ...
```

### スレッドモデル

```
メインスレッド:
  tk.Tk() → mainloop()
  └── VoiceOverlay: 描画更新、状態遷移

ワーカースレッド (daemon):
  ├── HotkeyListener (pynput): キー監視
  │     └── on_activate / on_deactivate コールバック
  ├── ContinuousRecognizer: Azure Speech SDK
  └── refine_text: Azure OpenAI API

スレッド間通信:
  ワーカー → GUI: root.after(0, callback) で安全にディスパッチ
```

### 変更対象: main.py

現在の`main.py`はメインスレッドで`listener.wait()`をブロッキング呼び出ししている。GUI統合後は：

1. `tk.Tk()`をメインスレッドで作成
2. `VoiceOverlay`を初期化
3. `HotkeyListener`をワーカースレッドで開始
4. `root.mainloop()`でメインスレッドをブロック
5. ホットキーコールバック内で`root.after()`を使いGUI更新

```python
# 概念的な構造（擬似コード）
def main():
    config = AppConfig()
    root = tk.Tk()
    overlay = VoiceOverlay(root)

    def on_activate():
        root.after(0, overlay.show, "recording")
        audio_monitor.start(lambda level: root.after(0, overlay.update_level, level))
        recognizer.start()

    def on_deactivate():
        root.after(0, overlay.show, "refining")
        audio_monitor.stop()
        text = recognizer.stop()
        text = refine_text(text, config.openai)
        paste_text(text)
        root.after(0, overlay.show, "done")
        root.after(1000, overlay.hide)

    listener = HotkeyListener(hotkey=config.hotkey, ...)
    threading.Thread(target=listener.start, daemon=True).start()
    root.mainloop()
```

## コンポーネント設計

### VoiceOverlay (src/gui.py)

```python
class VoiceOverlay:
    """ミニマルオーバーレイウィンドウ。"""

    def __init__(self, root: tk.Tk):
        """ウィンドウ初期化。非表示状態で開始。"""

    def show(self, state: str) -> None:
        """状態を変更して表示。
        state: "recording" | "refining" | "done"
        """

    def update_level(self, level: float) -> None:
        """サウンドレベルバーを更新。level: 0.0〜1.0"""

    def hide(self) -> None:
        """ウィンドウを非表示にする。"""
```

**ウィンドウ属性:**
- `overrideredirect(True)` — ボーダーレス
- `attributes('-topmost', True)` — 常に最前面
- macOS: `attributes('-alpha', 0.9)` — 半透明
- `withdraw()`/`deiconify()` — 表示/非表示切替

**レイアウト（tk.Canvas）:**
```
┌─────────────────────────────────────────┐
│ ● [サウンドレベルバー/プログレスバー] 0:05 │
└─────────────────────────────────────────┘
 ↑状態ドット   ↑中央コンテンツ          ↑経過時間
```

**プログレスバー（推敲中）:**
- 1.5秒固定で左端から右端まで塗りつぶし
- `root.after()`で16ms間隔更新（約60fps）
- 推敲が1.5秒以内に完了すればバーは途中で止まり「完了」へ遷移
- 推敲が1.5秒を超えた場合、バーは右端で留まり、完了を待つ

### AudioLevelMonitor (src/audio_level.py)

```python
class AudioLevelMonitor:
    """sounddeviceでマイクPCMデータからRMS値を計算。"""

    def __init__(self, device: int | None = None):
        """初期化。device=Noneでデフォルトマイク。"""

    def start(self, callback: Callable[[float], None]) -> None:
        """ストリーム開始。callbackにRMS値(0.0〜1.0)を通知。"""

    def stop(self) -> None:
        """ストリーム停止。"""
```

**実装詳細:**
- `sounddevice.InputStream(callback=...)` でPCMデータ取得
- コールバック間隔: 約30ms（`blocksize`で制御）
- RMS計算: numpy使用（sounddeviceの依存として自動インストールされる）
  ```python
  rms = float(np.sqrt(np.mean(indata ** 2)))
  ```
- 正規化: `min(rms / 0.1, 1.0)` で0.0〜1.0にクランプ（0.1は経験的閾値、調整可能）
- Azure Speech SDKとマイクを共有（macOS Core Audioは共有アクセス対応）
- GUI非表示時はストリームを停止してCPU節約

## 依存関係の追加

`requirements.txt`に追加:
```
sounddevice>=0.4.6
```

## コンソールUIとの共存

`src/ui.py`（コンソールUI）は変更せず残す。GUI起動時もコンソールにログが出力される。GUIはコンソールUIの置き換えではなく、補助的な可視化レイヤー。

## --onceモードの扱い

`--once`（シングルショットモード）ではGUIを表示しない。GUIは`run_continuous`（ホットキーモード）専用。

## エラーハンドリング

- sounddevice初期化失敗時: ログ警告を出してGUIのレベルバーを無効化（録音自体は継続）
- tkinter初期化失敗時（ヘッドレス環境等）: GUIなしでコンソールUIのみで動作（フォールバック）
- ワーカースレッドの例外: `root.after()`でGUIに伝搬し、エラー表示後にhide
