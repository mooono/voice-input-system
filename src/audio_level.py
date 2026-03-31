"""Audio level monitoring via sounddevice for GUI visualization."""

import logging
from typing import Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioLevelMonitor:
    """Capture microphone PCM data and compute RMS level for visualization."""

    def __init__(self, device: int | None = None, block_duration_ms: int = 30):
        self._device = device
        self._blocksize = int(16000 * block_duration_ms / 1000)
        self._stream: sd.InputStream | None = None
        self._callback: Callable[[float], None] | None = None

    def start(self, callback: Callable[[float], None]) -> None:
        """Start audio stream. callback receives RMS level 0.0-1.0."""
        self._callback = callback
        try:
            self._stream = sd.InputStream(
                device=self._device,
                channels=1,
                samplerate=16000,
                blocksize=self._blocksize,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info("Audio level monitor started")
        except Exception:
            logger.warning("Failed to start audio level monitor", exc_info=True)
            self._stream = None

    def stop(self) -> None:
        """Stop audio stream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            logger.info("Audio level monitor stopped")

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status,
    ) -> None:
        if status:
            logger.debug("Audio status: %s", status)
        rms = float(np.sqrt(np.mean(indata**2)))
        level = min(rms / 0.1, 1.0)
        if self._callback:
            self._callback(level)
