"""Tests for AudioLevelMonitor."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from src.audio_level import AudioLevelMonitor


class TestAudioLevelMonitor:
    def test_init_defaults(self):
        monitor = AudioLevelMonitor()
        assert monitor._device is None
        assert monitor._stream is None
        assert monitor._callback is None

    def test_rms_calculation(self):
        """Verify the audio callback computes correct RMS level."""
        monitor = AudioLevelMonitor()
        levels = []
        monitor._callback = lambda level: levels.append(level)

        amplitude = 0.05
        samples = np.full((480, 1), amplitude, dtype=np.float32)
        monitor._audio_callback(samples, 480, None, None)

        assert len(levels) == 1
        expected_level = min(amplitude / 0.1, 1.0)
        assert abs(levels[0] - expected_level) < 0.01

    def test_rms_clamp_to_one(self):
        """Level should be clamped to 1.0 for loud audio."""
        monitor = AudioLevelMonitor()
        levels = []
        monitor._callback = lambda level: levels.append(level)

        loud_samples = np.full((480, 1), 0.5, dtype=np.float32)
        monitor._audio_callback(loud_samples, 480, None, None)

        assert levels[0] == 1.0

    def test_silence_gives_zero(self):
        """Silent audio should give level ~0.0."""
        monitor = AudioLevelMonitor()
        levels = []
        monitor._callback = lambda level: levels.append(level)

        silent = np.zeros((480, 1), dtype=np.float32)
        monitor._audio_callback(silent, 480, None, None)

        assert levels[0] == 0.0

    @patch("src.audio_level.sd.InputStream")
    def test_start_creates_stream(self, mock_cls):
        monitor = AudioLevelMonitor()
        monitor.start(lambda level: None)
        mock_cls.assert_called_once()
        mock_cls.return_value.start.assert_called_once()

    @patch("src.audio_level.sd.InputStream")
    def test_stop_closes_stream(self, mock_cls):
        monitor = AudioLevelMonitor()
        monitor.start(lambda level: None)
        monitor.stop()
        mock_cls.return_value.stop.assert_called_once()
        mock_cls.return_value.close.assert_called_once()
        assert monitor._stream is None

    @patch("src.audio_level.sd.InputStream", side_effect=OSError("No device"))
    def test_start_handles_device_error(self, mock_cls):
        """Should not raise when audio device is unavailable."""
        monitor = AudioLevelMonitor()
        monitor.start(lambda level: None)
        assert monitor._stream is None
