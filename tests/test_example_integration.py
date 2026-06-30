"""Integration tests using bundled example data (water.h5).

Exercises the full pipeline (parser -> Structure -> VispyViewer -> export)
with real data shapes, catching regressions that unit tests (which use
1-2 atom _make_structure setups) would miss.
"""

from importlib.resources import files as resource_files
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vibview.config import Config
from vibview.core import Structure
from vibview.parsers import make_qpoint_loader
from vibview.parsers import parse as parse_file


class TestViewerFromExample:
    """Layer 1 — VispyViewer constructed from a real parsed example file."""

    pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")

    def test_viewer_creates_correct_scene(self):
        file = resource_files("vibview.examples").joinpath("water.h5")
        result = parse_file(file, "native")
        structure = Structure(result.data, qpoint_loader=make_qpoint_loader(result))

        from vibview.renderers.vispy_renderer import VispyViewer

        viewer = VispyViewer(
            structure,
            config=Config.defaults(),
            mode_type="animate",
            create_window=False,
        )

        assert len(viewer.scene.atoms.visuals) == 3
        assert len(viewer.scene.bonds.visuals) == 2
        assert len(viewer.structure.modes) == 9  # 3 atoms × 3 Cartesian DOF
        assert viewer.animation.frames.shape == (
            viewer.animation.frames_per_cycle,
            len(viewer.structure.atoms),
            3,
        )
        assert viewer.camera is not None
        assert viewer.scene.is_supercell is False


class TestExportFromExample:
    """Layer 2 — Export pipeline exercised with real example data."""

    pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")

    def _build_viewer(self):
        file = resource_files("vibview.examples").joinpath("water.h5")
        result = parse_file(file, "native")
        structure = Structure(result.data, qpoint_loader=make_qpoint_loader(result))

        from vibview.renderers.vispy_renderer import VispyViewer

        return VispyViewer(
            structure,
            config=Config.defaults(),
            mode_type="animate",
            create_window=False,
        )

    def test_export_png(self):
        viewer = self._build_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]
        viewer.export_animation(format="png", name="/tmp/test_export")

        self.mock_render_frames.assert_called_once()
        self.mock_save_png.assert_called_once()

    @pytest.mark.parametrize(
        ("fmt", "save_mock_attr"),
        [
            ("png", "mock_save_png"),
            ("gif", "mock_save_gif"),
            ("mp4", "mock_save_mp4"),
        ],
    )
    def test_export_all_formats(self, fmt, save_mock_attr):
        viewer = self._build_viewer()
        self.mock_render_frames.return_value = [np.zeros((4, 4, 4), dtype=np.uint8)]

        save_mock = getattr(self, save_mock_attr)
        viewer.export_animation(format=fmt, name=f"/tmp/test_{fmt}")

        self.mock_render_frames.assert_called_once()
        save_mock.assert_called_once()


class TestMainExportDispatch:
    """Layer 3 — Integration tests for the main() CLI dispatch."""

    def test_export_from_example_via_main(self):
        from vibview.main import main

        test_file = resource_files("vibview.examples").joinpath("water.h5")

        with (
            patch("vibview.main.parse_file") as mock_parse,
            patch("vibview.main.make_qpoint_loader"),
            patch("vibview.main.Structure"),
            patch("vibview.main.VispyViewer") as mock_viewer_cls,
        ):
            mock_viewer = mock_viewer_cls.return_value
            mock_parse.return_value = MagicMock()

            exit_code = main(
                [
                    "export",
                    str(test_file),
                    "native",
                    "--format",
                    "png",
                    "--name",
                    "/tmp/out",
                ]
            )

        assert exit_code == 0
        mock_parse.assert_called_once()
        mock_viewer_cls.assert_called_once()
        mock_viewer.export_animation.assert_called_once_with(
            format="png", name="/tmp/out"
        )

    def test_export_returns_nonzero_on_parse_error(self):
        from vibview.main import main

        with patch("vibview.main.parse_file") as mock_parse:
            mock_parse.side_effect = FileNotFoundError("no such file")

            exit_code = main(
                [
                    "export",
                    "nonexistent.h5",
                    "native",
                    "--format",
                    "png",
                    "--name",
                    "/tmp/out",
                ]
            )

        assert exit_code == 1

    def test_view_without_file_loads_example(self):
        from vibview.main import main

        with (
            patch("vibview.main.parse_file") as mock_parse,
            patch("vibview.main.make_qpoint_loader"),
            patch("vibview.main.Structure"),
            patch("vibview.main.VispyViewer"),
        ):
            mock_parse.return_value = MagicMock()

            exit_code = main(["view"])

        assert exit_code == 0
        mock_parse.assert_called_once()

    def test_view_with_example_flag_loads_bundled(self):
        from vibview.main import main

        with (
            patch("vibview.main.parse_file") as mock_parse,
            patch("vibview.main.make_qpoint_loader"),
            patch("vibview.main.Structure"),
            patch("vibview.main.VispyViewer"),
        ):
            mock_parse.return_value = MagicMock()

            exit_code = main(["view", "--example", "diamond"])

        assert exit_code == 0
        mock_parse.assert_called_once()
        loaded_path = mock_parse.call_args[0][0]
        assert "diamond" in str(loaded_path)

    def test_view_with_unknown_example_errors(self):
        from vibview.main import main

        exit_code = main(["view", "--example", "nonexistent"])
        assert exit_code == 1


class TestDiamondExample:
    """Integration tests using the bundled diamond crystal example."""

    pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")

    def test_viewer_creates_crystal_scene(self):
        file = resource_files("vibview.examples").joinpath("diamond.h5")
        result = parse_file(file, "native")
        structure = Structure(result.data, qpoint_loader=make_qpoint_loader(result))

        from vibview.renderers.vispy_renderer import VispyViewer

        viewer = VispyViewer(
            structure,
            config=Config.defaults(),
            mode_type="animate",
            create_window=False,
        )

        assert len(viewer.scene.atoms.visuals) == 2
        assert len(viewer.structure.modes) == 6  # 2 atoms × 3 Cartesian DOF
        assert viewer.scene.is_supercell is False

    def test_qpoint_switching(self):
        file = resource_files("vibview.examples").joinpath("diamond.h5")
        result = parse_file(file, "native")
        structure = Structure(result.data, qpoint_loader=make_qpoint_loader(result))

        structure.switch_qpoint(10)
        assert len(structure.modes) == 6

        structure.switch_qpoint(0)
        assert structure.modes[3].frequency is not None
