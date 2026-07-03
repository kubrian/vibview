"""Tests for CameraController: quaternion helpers, HUD, and camera pose."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.conftest import _make_structure
from vibview.config import Config
from vibview.models import Atom, Mode
from vibview.renderers.camera_controller import CameraController

pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")


class TestBuildQuaternion:
    """Tests for CameraController._build_quaternion (static method).

    Convention: az=0°, el=0° orients the camera forward along +y.
    """

    def test_forward_at_zero_zero(self):
        q = CameraController._build_quaternion(0.0, 0.0)
        m = np.array(q.get_matrix())[:3, :3]
        forward = -m[:, 2]
        np.testing.assert_allclose(forward, [0.0, 1.0, 0.0], atol=1e-6)

    def test_forward_at_azimuth_90(self):
        q = CameraController._build_quaternion(90.0, 0.0)
        m = np.array(q.get_matrix())[:3, :3]
        forward = -m[:, 2]
        np.testing.assert_allclose(forward, [1.0, 0.0, 0.0], atol=1e-6)

    def test_forward_at_elevation_90(self):
        q = CameraController._build_quaternion(0.0, 90.0)
        m = np.array(q.get_matrix())[:3, :3]
        forward = -m[:, 2]
        np.testing.assert_allclose(forward, [0.0, 0.0, 1.0], atol=1e-6)

    def test_forward_at_elevation_neg90(self):
        q = CameraController._build_quaternion(0.0, -90.0)
        m = np.array(q.get_matrix())[:3, :3]
        forward = -m[:, 2]
        np.testing.assert_allclose(forward, [0.0, 0.0, -1.0], atol=1e-6)

    def test_roundtrip(self):
        azi, ele = 45.0, 30.0
        q = CameraController._build_quaternion(azi, ele)
        azi2, ele2 = CameraController._quaternion_to_ae(q)
        assert azi2 == pytest.approx(azi, abs=1e-4)
        assert ele2 == pytest.approx(ele, abs=1e-4)

    def test_roundtrip_negative_values(self):
        azi, ele = -120.0, -45.0
        q = CameraController._build_quaternion(azi, ele)
        azi2, ele2 = CameraController._quaternion_to_ae(q)
        assert azi2 == pytest.approx(azi, abs=1e-4)
        assert ele2 == pytest.approx(ele, abs=1e-4)

    def test_roundtrip_near_poles(self):
        """Elevation near ±90° rounds to exactly ±90° (cos_angle threshold)."""
        for ele_in, ele_out in [(89.9, 90.0), (-89.9, -90.0)]:
            q = CameraController._build_quaternion(30.0, ele_in)
            azi2, ele2 = CameraController._quaternion_to_ae(q)
            assert ele2 == pytest.approx(ele_out, abs=1e-2)

    def test_roundtrip_varied_azimuths(self):
        for azi in [0.0, 45.0, 90.0, 180.0, -90.0]:
            q = CameraController._build_quaternion(azi, 20.0)
            azi2, ele2 = CameraController._quaternion_to_ae(q)
            assert azi2 == pytest.approx(azi, abs=1e-4)
            assert ele2 == pytest.approx(20.0, abs=1e-4)

    def test_roundtrip_270_deg_equivalent_to_neg90(self):
        q = CameraController._build_quaternion(270.0, 20.0)
        azi2, ele2 = CameraController._quaternion_to_ae(q)
        assert azi2 == pytest.approx(-90.0, abs=1e-4)


class TestQuaternionToAE:
    """Tests for CameraController._quaternion_to_ae (static method)."""

    def test_identity_forward_negative_z(self):
        """Identity quaternion: forward = -z → el = -90°, az is arbitrary."""
        q = MagicMock()
        q.get_matrix.return_value = np.eye(4, dtype=np.float64)
        azi, ele = CameraController._quaternion_to_ae(q)
        assert ele == pytest.approx(-90.0, abs=1.0)

    def test_degenerate_forward_returns_zero(self):
        q = MagicMock()
        m = np.eye(4, dtype=np.float64)
        m[:3, 2] = [0.0, 0.0, 0.0]
        q.get_matrix.return_value = m
        azi, ele = CameraController._quaternion_to_ae(q)
        assert azi == 0.0
        assert ele == 0.0

    def test_known_azimuth_elevation(self):
        q = CameraController._build_quaternion(127.3, 24.1)
        azi, ele = CameraController._quaternion_to_ae(q)
        assert azi == pytest.approx(127.3, abs=1e-4)
        assert ele == pytest.approx(24.1, abs=1e-4)


class TestToggleHUD:
    """Tests for CameraController.toggle_hud."""

    def _controller(self, **kwargs):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        modes = [Mode([[1.0, 0.0, 0.0]], frequency=0.0)]
        structure = _make_structure(atoms, modes)
        cfg = Config.defaults()
        for k, v in kwargs.items():
            setattr(cfg.camera, k, v)
        return CameraController(structure, cfg)

    def test_toggle_turns_on(self):
        ctrl = self._controller()
        ctrl._hud_visible = False
        ctrl._hud_view.visible = False
        ctrl.toggle_hud()
        assert ctrl._hud_visible is True
        assert ctrl._hud_view.visible is True

    def test_toggle_turns_off(self):
        ctrl = self._controller()
        ctrl._hud_visible = True
        ctrl._hud_view.visible = True
        ctrl.toggle_hud()
        assert ctrl._hud_visible is False
        assert ctrl._hud_view.visible is False

    def test_toggle_calls_canvas_update(self):
        ctrl = self._controller()
        ctrl.canvas.update = MagicMock()
        ctrl.toggle_hud()
        ctrl.canvas.update.assert_called_once()

    def test_initial_state_from_config_false(self):
        ctrl = self._controller(show_hud=False)
        assert ctrl._hud_visible is False

    def test_initial_state_from_config_true(self):
        ctrl = self._controller(show_hud=True)
        assert ctrl._hud_visible is True


class TestCameraPose:
    """Tests for config-driven initial camera pose."""

    def test_explicit_center(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(atoms, [Mode([[1.0, 0.0, 0.0]], frequency=0.0)])
        cfg = Config.defaults()
        cfg.camera.center = (5.0, 6.0, 7.0)
        CameraController(structure, cfg)
        _, kwargs = self.mock_camera.call_args_list[0]
        np.testing.assert_array_equal(kwargs["center"], [5.0, 6.0, 7.0])

    def test_explicit_distance(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(atoms, [Mode([[1.0, 0.0, 0.0]], frequency=0.0)])
        cfg = Config.defaults()
        cfg.camera.distance = 25.0
        CameraController(structure, cfg)
        _, kwargs = self.mock_camera.call_args_list[0]
        assert kwargs["distance"] == 25.0

    def test_explicit_azimuth_elevation_applied(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(atoms, [Mode([[1.0, 0.0, 0.0]], frequency=0.0)])
        cfg = Config.defaults()
        cfg.camera.azimuth = 90.0
        cfg.camera.elevation = 45.0
        ctrl = CameraController(structure, cfg)
        azi2, ele2 = CameraController._quaternion_to_ae(ctrl.view.camera._quaternion)
        assert azi2 == pytest.approx(90.0, abs=1e-4)
        assert ele2 == pytest.approx(45.0, abs=1e-4)

    def test_auto_center_uses_centroid(self):
        atoms = [Atom("O", [2.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 4.0])]
        structure = _make_structure(
            atoms, [Mode([[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]], frequency=0.0)]
        )
        cfg = Config.defaults()
        CameraController(structure, cfg)
        _, kwargs = self.mock_camera.call_args_list[0]
        np.testing.assert_array_equal(kwargs["center"], [1.0, 0.0, 2.0])

    def test_auto_distance_positive(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        structure = _make_structure(
            atoms, [Mode([[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]], frequency=0.0)]
        )
        cfg = Config.defaults()
        CameraController(structure, cfg)
        _, kwargs = self.mock_camera.call_args_list[0]
        assert kwargs["distance"] >= cfg.camera.min_distance

    def test_azimuth_auto_uses_default_orientation(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(atoms, [Mode([[1.0, 0.0, 0.0]], frequency=0.0)])
        cfg = Config.defaults()
        ctrl = CameraController(structure, cfg)
        assert ctrl.view.camera._quaternion is not None
