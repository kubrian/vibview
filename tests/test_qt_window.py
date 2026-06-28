"""Tests for the main window (VibviewWindow)."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QSplitter, QWidget

from vibview.models import Mode
from vibview.renderers.qt_window import ModeSelectorPanel, VibviewWindow


@pytest.fixture(autouse=True)
def _mock_canvas(_qapp):
    canvas = MagicMock()
    canvas.native = QWidget()
    return canvas


class TestVibviewWindow:
    def test_central_widget_is_splitter(self, _mock_canvas):
        win = VibviewWindow(_mock_canvas, [Mode(0, [[0.0, 0.0, 0.0]])])
        cw = win.centralWidget()
        assert isinstance(cw, QSplitter)
        assert cw.orientation() == Qt.Orientation.Horizontal

    def test_splitter_contains_panel_and_canvas(self, _mock_canvas):
        win = VibviewWindow(_mock_canvas, [Mode(0, [[0.0, 0.0, 0.0]])])
        splitter = win.centralWidget()
        assert splitter.count() == 2
        assert isinstance(splitter.widget(0), ModeSelectorPanel)
        assert splitter.widget(1) is _mock_canvas.native

    def test_f11_toggles_full_screen(self, _mock_canvas):
        win = VibviewWindow(_mock_canvas, [Mode(0, [[0.0, 0.0, 0.0]])])
        with (
            patch.object(win, "showFullScreen") as mock_show_fs,
            patch.object(win, "showNormal") as mock_show_normal,
        ):
            event_fs = QKeyEvent(
                QKeyEvent.Type.KeyPress, Qt.Key.Key_F11, Qt.KeyboardModifier.NoModifier
            )
            win.keyPressEvent(event_fs)
            mock_show_fs.assert_called_once()

            win.isFullScreen = MagicMock(return_value=True)
            win.keyPressEvent(event_fs)
            mock_show_normal.assert_called_once()

    def test_r_key_calls_camera_reset_callback(self, _mock_canvas):
        win = VibviewWindow(_mock_canvas, [Mode(0, [[0.0, 0.0, 0.0]])])
        reset = MagicMock()
        win.on_camera_reset = reset
        event_r = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier
        )
        win.keyPressEvent(event_r)
        reset.assert_called_once()

    def test_r_key_no_callback_does_not_crash(self, _mock_canvas):
        win = VibviewWindow(_mock_canvas, [Mode(0, [[0.0, 0.0, 0.0]])])
        event_r = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier
        )
        win.keyPressEvent(event_r)

    def test_window_title(self, _mock_canvas):
        win = VibviewWindow(_mock_canvas, [Mode(0, [[0.0, 0.0, 0.0]])])
        assert win.windowTitle() == "VibView"


class TestVibviewWindowModes:
    def test_modes_passed_to_panel(self, _mock_canvas):
        modes = [
            Mode(0, [[1.0, 0.0, 0.0]]),
            Mode(1, [[0.0, 1.0, 0.0]], frequency=500.0, label="test"),
        ]
        win = VibviewWindow(_mock_canvas, modes)
        assert win.panel.table.rowCount() == 2
