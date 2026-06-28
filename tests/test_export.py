"""Tests for animation export (PNG sequence, GIF, MP4)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tests.conftest import _make_structure
from vibview.config import Config
from vibview.models import Atom, Mode
from vibview.renderers.export import (
    render_frames,
    save_gif,
    save_mp4,
    save_png_sequence,
)


def _make_dummy_images(n: int, h: int = 4, w: int = 4) -> list[np.ndarray]:
    rng = np.random.default_rng(42)
    return [rng.integers(0, 256, size=(h, w, 4), dtype=np.uint8) for _ in range(n)]


class TestSavePngSequence:
    def test_saves_png_files(self, tmp_path: Path):
        images = _make_dummy_images(3)
        name = str(tmp_path / "anim")
        paths = save_png_sequence(images, name)
        assert len(paths) == 3
        for p in paths:
            assert p.exists()
            assert p.suffix == ".png"
            assert p.stat().st_size > 0

    def test_returns_correct_number_of_paths(self, tmp_path: Path):
        images = _make_dummy_images(5)
        name = str(tmp_path / "anim")
        paths = save_png_sequence(images, name)
        assert len(paths) == 5

    def test_uses_name_prefix(self, tmp_path: Path):
        images = _make_dummy_images(10)
        name = str(tmp_path / "my_anim")
        paths = save_png_sequence(images, name)
        assert paths[0].name == "my_anim_00.png"
        assert paths[9].name == "my_anim_09.png"


class TestSaveGif:
    def test_saves_gif_file(self, tmp_path: Path):
        images = _make_dummy_images(3)
        out = tmp_path / "anim.gif"
        path = save_gif(images, str(out), duration=100)
        assert path.exists()
        assert path.suffix == ".gif"


class TestSaveMp4:
    def test_raises_if_ffmpeg_missing(self, tmp_path: Path):
        images = _make_dummy_images(3)
        out = tmp_path / "anim.mp4"
        with (
            patch("vibview.renderers.export.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="ffmpeg"),
        ):
            save_mp4(images, str(out), fps=30)

    def test_calls_imageio_when_ffmpeg_present(self, tmp_path: Path):
        images = _make_dummy_images(3, h=4, w=4)
        out = tmp_path / "anim.mp4"
        with (
            patch(
                "vibview.renderers.export.shutil.which", return_value="/usr/bin/ffmpeg"
            ),
            patch("imageio.v3.imwrite") as mock_iio,
        ):
            save_mp4(images, str(out), fps=30)
        mock_iio.assert_called_once()
        args, kwargs = mock_iio.call_args
        assert Path(args[0]) == out
        assert kwargs["fps"] == 30


class TestRenderFrames:
    def test_calls_apply_for_each_frame(self):
        canvas = MagicMock()
        canvas.render.return_value = np.zeros((4, 4, 4), dtype=np.uint8)
        apply_fn = MagicMock()
        frames = np.zeros((5, 3, 3))

        render_frames(canvas, frames, apply_fn)

        assert apply_fn.call_count == 5
        for i in range(5):
            apply_fn.assert_any_call(i)

    def test_returns_one_image_per_frame(self):
        canvas = MagicMock()
        canvas.render.return_value = np.zeros((4, 4, 4), dtype=np.uint8)
        frames = np.zeros((3, 2, 3))

        images = render_frames(canvas, frames, lambda i: None)

        assert len(images) == 3
        for img in images:
            assert img.shape == (4, 4, 4)

    def test_zero_frames_returns_empty_list(self):
        canvas = MagicMock()
        canvas.render.return_value = np.zeros((4, 4, 4), dtype=np.uint8)
        frames = np.zeros((0, 2, 3))

        images = render_frames(canvas, frames, lambda i: None)

        assert images == []


class TestExportAnimationOnViewer:
    """Test the export_animation method on VispyViewer (mocked)."""

    pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")

    def _make_viewer(self):
        from vibview.renderers.vispy_renderer import VispyViewer

        return VispyViewer(
            _make_structure([Atom("O", [0.0, 0.0, 0.0])], [Mode(0, [[1.0, 0.0, 0.0]])]),
            config=Config.defaults(),
            mode_type="animate",
        )

    def test_export_png_calls_save_png_sequence(self, tmp_path: Path):
        viewer = self._make_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        name = str(tmp_path / "anim")
        viewer.export_animation(format="png", name=name)
        self.mock_render_frames.assert_called_once()
        self.mock_save_png.assert_called_once()
        args, _ = self.mock_save_png.call_args
        assert args[1] == name

    def test_export_gif_calls_save_gif(self, tmp_path: Path):
        viewer = self._make_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        name = str(tmp_path / "anim")
        viewer.export_animation(format="gif", name=name)
        self.mock_save_gif.assert_called_once()
        args, kwargs = self.mock_save_gif.call_args
        assert args[1] == f"{name}.gif"
        assert kwargs.get("duration") == pytest.approx(100.0)

    def test_export_mp4_calls_save_mp4(self, tmp_path: Path):
        viewer = self._make_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        name = str(tmp_path / "anim")
        viewer.export_animation(format="mp4", name=name)
        self.mock_save_mp4.assert_called_once()
        args, kwargs = self.mock_save_mp4.call_args
        assert args[1] == f"{name}.mp4"
        assert kwargs.get("fps") == 60

    def test_export_uses_frames_per_cycle(self):
        viewer = self._make_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        viewer.export_animation(format="png", name="/tmp/out")
        args, _ = self.mock_render_frames.call_args
        frames_arg = args[1]
        assert len(frames_arg) == viewer.animation.frames_per_cycle

    def test_export_cycles_multiplies_frames(self):
        viewer = self._make_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        viewer.export_animation(format="png", name="/tmp/out", cycles=3)
        args, _ = self.mock_render_frames.call_args
        frames_arg = args[1]
        assert len(frames_arg) == viewer.animation.frames_per_cycle * 3

    @pytest.mark.parametrize(
        "fmt, fps_attr, expected_fps",
        [("gif", "gif_fps", 10), ("mp4", "mp4_fps", 60)],
    )
    def test_export_fps_per_format(self, fmt, fps_attr, expected_fps):
        viewer = self._make_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        fps = getattr(viewer, fps_attr)
        expected_frames = max(int(round(fps * viewer.period)), 2)
        viewer.export_animation(format=fmt, name="/tmp/out")
        args, _ = self.mock_render_frames.call_args
        frames_arg = args[1]
        assert len(frames_arg) == expected_frames

    def test_export_restores_original_frames(self):
        viewer = self._make_viewer()
        original_frames = viewer.animation.frames.copy()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        viewer.export_animation(format="gif", name="/tmp/out")
        np.testing.assert_array_equal(viewer.animation.frames, original_frames)
