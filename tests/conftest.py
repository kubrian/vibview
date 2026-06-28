"""Shared fixtures and helpers for vibview tests."""

from unittest.mock import MagicMock, patch

import pytest

from vibview.core import Structure
from vibview.models import VibData


def _make_structure(atoms, modes):
    """Build a Structure from Atom and Mode lists."""
    internal = VibData(atoms, modes)
    return Structure(internal)


def _make_structure_with_lattice(atoms, modes, lattice):
    """Build a Structure with lattice vectors."""
    internal = VibData(atoms, modes, lattice=lattice)
    return Structure(internal)


class _MockMesh:
    """Mock Mesh that quacks like vispy Mesh without Node parent validation."""

    def __init__(self, meshdata=None, color=None, parent=None, shading=None):
        self.meshdata = meshdata
        self._color = color
        self.transform = None

    @property
    def events(self):
        return MagicMock()

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value

    def update(self):
        pass


@pytest.fixture(scope="session")
def _qapp():
    """Session-scoped QApplication for Qt-dependent tests."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def _mock_qt_window():
    """Patch VibviewWindow in the vispy_renderer module."""
    with patch("vibview.renderers.vispy_renderer.VibviewWindow"):
        yield


@pytest.fixture
def _patch_vispy(request):
    """Patch vispy components for renderer tests.

    Sets mock attributes on the test class instance (request.instance)
    so tests can access self.mock_sphere, self.mock_tube, etc.

    Most vispy components are patched at the ``vispy.*`` package level
    (since the code accesses them via module attribute lookup).  A few
    by-value imports (``create_cone``, ``ViewBox``, etc.) are patched
    per-module.
    """
    mock_create_cone_shared = MagicMock(return_value=MagicMock())

    import numpy as np

    _mock_transform = MagicMock()
    _mock_transform.matrix = np.eye(4, dtype=np.float64)

    with (
        # vispy-level patches (module attribute lookups)
        patch("vispy.scene.SceneCanvas") as mock_canvas,
        patch("vispy.scene.cameras.ArcballCamera") as mock_camera,
        patch("vispy.scene.visuals.Sphere") as mock_sphere,
        patch("vispy.scene.visuals.Tube") as mock_tube,
        patch("vispy.scene.visuals.Mesh") as mock_mesh,
        patch("vispy.scene.visuals.Text") as mock_text,
        patch("vispy.scene.transforms.STTransform") as mock_st,
        patch("vispy.scene.transforms.MatrixTransform") as mock_mtr,
        patch("vispy.app.Timer") as mock_timer,
        # by-value imports (shared mock for create_cone across modules)
        patch(
            "vibview.renderers._geometry.create_cone",
            new=mock_create_cone_shared,
        ),
        # module-specific by-value imports
        patch("vibview.renderers.camera_controller.ViewBox"),
        # render_frames is imported at module level in animation_controller
        patch(
            "vibview.renderers.animation_controller.render_frames"
        ) as mock_render_frames,
        # vispy_renderer export patches (by-value imports in vispy_renderer)
        patch("vibview.renderers.vispy_renderer.save_png_sequence") as mock_save_png,
        patch("vibview.renderers.vispy_renderer.save_gif") as mock_save_gif,
        patch("vibview.renderers.vispy_renderer.save_mp4") as mock_save_mp4,
    ):
        mock_mtr.side_effect = lambda: MagicMock()
        mock_mesh.side_effect = _MockMesh
        # Configure mock canvas and camera instances
        mock_canvas.return_value.size = (608, 608)
        mock_camera.return_value.transform = _mock_transform
        mock_camera.return_value.center = (0.0, 0.0, 0.0)
        mock_camera.return_value.distance = 10.0
        request.instance.mock_canvas = mock_canvas
        request.instance.mock_camera = mock_camera
        request.instance.mock_sphere = mock_sphere
        request.instance.mock_tube = mock_tube
        request.instance.mock_mesh = mock_mesh
        request.instance.mock_text = mock_text
        request.instance.mock_create_cone = mock_create_cone_shared
        request.instance.mock_st_transform = mock_st
        request.instance.mock_mtr = mock_mtr
        request.instance.mock_timer = mock_timer
        request.instance.mock_render_frames = mock_render_frames
        request.instance.mock_save_png = mock_save_png
        request.instance.mock_save_gif = mock_save_gif
        request.instance.mock_save_mp4 = mock_save_mp4
        yield
