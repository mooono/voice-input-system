"""Tests for VoiceOverlay (headless-safe using mock tk)."""

from unittest.mock import MagicMock, patch


class TestVoiceOverlay:
    def _make_overlay(self):
        """Create a VoiceOverlay with a mocked Tk root."""
        mock_root = MagicMock()
        mock_root.winfo_screenwidth.return_value = 1920
        mock_canvas = MagicMock()
        mock_canvas.create_oval.return_value = 1
        mock_canvas.create_rectangle.side_effect = [2, 3]
        mock_canvas.create_text.return_value = 4

        with patch("src.gui.tk.Canvas", return_value=mock_canvas):
            from src.gui import VoiceOverlay

            ov = VoiceOverlay(mock_root)

        return ov, mock_root, mock_canvas

    def test_initial_state_hidden(self):
        ov, root, _ = self._make_overlay()
        assert ov._state == "hidden"
        root.attributes.assert_any_call("-alpha", 0.0)

    def test_show_recording(self):
        ov, root, _ = self._make_overlay()
        ov.show("recording")
        assert ov._state == "recording"
        root.attributes.assert_any_call("-alpha", 0.9)

    def test_show_refining(self):
        ov, root, _ = self._make_overlay()
        ov.show("refining")
        assert ov._state == "refining"

    def test_show_done_schedules_hide(self):
        ov, root, _ = self._make_overlay()
        ov.show("done")
        assert ov._state == "done"
        root.after.assert_called()

    def test_hide(self):
        ov, root, _ = self._make_overlay()
        ov.show("recording")
        ov.hide()
        assert ov._state == "hidden"
        root.attributes.assert_any_call("-alpha", 0.0)

    def test_update_level_during_recording(self):
        ov, _, canvas = self._make_overlay()
        ov._state = "recording"
        canvas.coords.reset_mock()
        ov.update_level(0.5)
        canvas.coords.assert_called()

    def test_update_level_ignored_when_not_recording(self):
        ov, _, canvas = self._make_overlay()
        ov._state = "refining"
        canvas.coords.reset_mock()
        ov.update_level(0.5)
        canvas.coords.assert_not_called()

    def test_update_level_clamp(self):
        ov, _, canvas = self._make_overlay()
        ov._state = "recording"
        ov.update_level(1.5)  # should clamp to 1.0
        ov.update_level(-0.5)  # should clamp to 0.0
        # No exception expected
