"""Audio capture module.

Provides microphone audio streaming using the Azure Speech SDK's
built-in audio input, so no extra audio library is needed.
"""

import azure.cognitiveservices.speech as speechsdk

from .config import AzureSpeechConfig


def create_audio_config() -> speechsdk.audio.AudioConfig:
    """Create an AudioConfig that reads from the default microphone."""
    return speechsdk.audio.AudioConfig(use_default_microphone=True)
