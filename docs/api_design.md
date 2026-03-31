# API Design

## Speech Recognition Module

### Function
recognize_once() -> str

### Function
recognize_continuous() -> str

## Text Refinement Module

### Function
refine_text(input_text: str) -> str

## Output Module

### Function
paste_text(text: str) -> None

## Controller

### Flow
1. Wait for hotkey
2. Call recognition
3. Optionally refine
4. Show confirmation
5. Paste text
