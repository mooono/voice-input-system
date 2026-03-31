"""Speech recognition module using Azure Speech-to-Text.

Provides single-shot and continuous recognition.
"""

import logging
import threading
from typing import Callable

import azure.cognitiveservices.speech as speechsdk

from .audio import create_audio_config
from .config import AzureSpeechConfig

logger = logging.getLogger(__name__)


def _create_speech_config(cfg: AzureSpeechConfig) -> speechsdk.SpeechConfig:
    speech_config = speechsdk.SpeechConfig(
        subscription=cfg.subscription_key,
        region=cfg.region,
    )
    speech_config.speech_recognition_language = cfg.language
    return speech_config


def recognize_once(cfg: AzureSpeechConfig) -> str:
    """Single-shot recognition — listens until a pause is detected."""
    speech_config = _create_speech_config(cfg)
    audio_config = create_audio_config()
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    logger.info("Listening (single-shot)…")
    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        logger.info("Recognized: %d chars", len(result.text))
        return result.text
    if result.reason == speechsdk.ResultReason.NoMatch:
        logger.warning("No speech detected")
        return ""
    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        logger.error("Recognition canceled: %s", details.reason)
        if details.reason == speechsdk.CancellationReason.Error:
            logger.error("Error details: %s", details.error_details)
        return ""
    return ""


class ContinuousRecognizer:
    """Continuous recognition with partial / final callbacks."""

    def __init__(
        self,
        cfg: AzureSpeechConfig,
        on_partial: Callable[[str], None] | None = None,
        on_final: Callable[[str], None] | None = None,
    ):
        self._cfg = cfg
        self._on_partial = on_partial
        self._on_final = on_final
        self._recognizer: speechsdk.SpeechRecognizer | None = None
        self._done = threading.Event()
        self._segments: list[str] = []

    def start(self) -> None:
        speech_config = _create_speech_config(self._cfg)
        audio_config = create_audio_config()
        self._recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )
        self._segments.clear()
        self._done.clear()

        self._recognizer.recognizing.connect(self._on_recognizing)
        self._recognizer.recognized.connect(self._on_recognized)
        self._recognizer.canceled.connect(self._on_canceled)
        self._recognizer.session_stopped.connect(self._on_session_stopped)

        self._recognizer.start_continuous_recognition()
        logger.info("Continuous recognition started")

    def stop(self) -> str:
        if self._recognizer:
            self._recognizer.stop_continuous_recognition()
            self._done.wait(timeout=5)
            self._recognizer = None
        return "".join(self._segments)

    # -- event handlers --

    def _on_recognizing(self, evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        if self._on_partial:
            self._on_partial(evt.result.text)

    def _on_recognized(self, evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        text = evt.result.text
        if text:
            self._segments.append(text)
            if self._on_final:
                self._on_final(text)

    def _on_canceled(self, evt: speechsdk.SpeechRecognitionCanceledEventArgs) -> None:
        details = evt.cancellation_details
        if details.reason == speechsdk.CancellationReason.Error:
            logger.error("Recognition error: %s", details.error_details)
        self._done.set()

    def _on_session_stopped(self, evt) -> None:
        self._done.set()
