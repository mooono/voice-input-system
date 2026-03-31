# Architecture

## High-Level Flow

1. User presses hotkey
2. Audio is captured from microphone
3. Audio is streamed to Azure Speech Service
4. Transcription is returned (partial + final)
5. (Optional) Text is refined via Azure OpenAI
6. Text is displayed for confirmation
7. Text is inserted into the active window

## Components

### Client (Windows)
- Audio capture
- Hotkey listener
- UI (console or overlay)
- Text injection

### Cloud Services
- Azure Speech-to-Text
- Azure OpenAI (optional)

## Data Flow

Client → Azure Speech → (Optional OpenAI) → Client

## Networking

- Use secure HTTPS (TLS)
- Prefer Private Endpoint if available
