"""Shared fixtures and helpers for vibview tests."""

from unittest.mock import MagicMock, patch

import h5py
import numpy as np
import pytest

from vibview.config import Config
from vibview.core import Structure
from vibview.models import VibData


def _make_structure(atoms, modes):
    """Build a Structure from Atom and Mode lists."""
    internal = VibData(atoms, modes, frequency_units="?")
    return Structure(internal, qpoint_loader=None)


def _make_structure_with_lattice(atoms, modes, lattice):
    """Build a Structure with lattice vectors and Gamma-point q-point."""
    internal = VibData(
        atoms,
        modes,
        lattice=lattice,
        qpoints=[[0.0, 0.0, 0.0]],
        frequency_units="?",
    )
    return Structure(internal, qpoint_loader=None)


def _make_viewer(structure, **kwargs):
    """Build a VispyViewer with config defaults."""
    from vibview.renderers.vispy_renderer import VispyViewer

    defaults = dict(config=Config.defaults(), mode_type="static")
    defaults.update(kwargs)
    return VispyViewer(structure, **defaults)


def _export(viewer, fmt, name, **kwargs):
    """Call viewer.export_animation with default cycles=1, progress_callback=None."""
    defaults = dict(cycles=1, progress_callback=None)
    defaults.update(kwargs)
    viewer.export_animation(format=fmt, name=name, **defaults)


def _make_crystal_h5(path, n_qpoints=2, n_bands=2, n_atoms=2, labels=None):
    """Write a minimal crystal HDF5 file with q-points and eigenvectors."""
    ev = np.zeros((n_qpoints, n_bands, n_atoms, 3, 2), dtype=np.float16)
    for qi in range(n_qpoints):
        for bi in range(n_bands):
            ev[qi, bi, 0, 0, 0] = float(qi * n_bands + bi + 1)
    freq = np.zeros((n_qpoints, n_bands), dtype=np.float64)
    freq[0, 0] = 100.0
    freq[1, 1] = 200.0
    qpoints = np.array([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]], dtype=np.float64)
    lattice = np.array(
        [[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]], dtype=np.float64
    )
    symbols = np.array(["O", "H"] * (n_atoms // 2) + ["O"], dtype=h5py.string_dtype())[
        :n_atoms
    ]
    positions = np.zeros((n_atoms, 3), dtype=np.float64)
    with h5py.File(path, "w") as f:
        g = f.create_group("atoms")
        g.create_dataset("symbols", data=symbols)
        g.create_dataset("positions", data=positions)
        g = f.create_group("modes")
        g.create_dataset("eigenvectors", data=ev)
        g.create_dataset("frequencies", data=freq)
        g["frequencies"].attrs["units"] = "THz"
        if labels is not None:
            g.create_dataset("labels", data=labels)
        f.create_dataset("lattice", data=lattice)
        f.create_dataset("qpoints", data=qpoints)


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
