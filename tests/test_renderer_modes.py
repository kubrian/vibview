"""Tests for mode switching, amplitude/period changes, and callbacks."""

import pytest

from tests.conftest import _make_structure
from vibview.config import Config
from vibview.models import Atom, Mode
from vibview.renderers.vispy_renderer import VispyViewer

pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")


class TestSwitchMode:
    """Tests for switching between vibrational modes."""

    def test_reuses_spheres(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        modes = [
            Mode(0, [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]]),
            Mode(1, [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]),
        ]
        structure = _make_structure(atoms, modes)
        cfg = Config.defaults()
        viewer = VispyViewer(structure, config=cfg, mode_type="static")

        old_spheres = list(viewer.scene.atoms.visuals)
        old_bonds = list(viewer.scene.bonds.visuals)
        old_transforms = [a.transform for a in viewer.scene.atoms.visuals]
        old_bond_transforms = list(viewer.scene.bonds.transforms)
        n_spheres = len(self.mock_sphere.call_args_list)

        viewer.switch_mode(1)

        assert viewer.scene.atoms.visuals == old_spheres
        assert viewer.scene.bonds.visuals == old_bonds
        assert all(
            a.transform is t for a, t in zip(viewer.scene.atoms.visuals, old_transforms)
        )
        assert viewer.scene.bonds.transforms == old_bond_transforms
        assert len(self.mock_sphere.call_args_list) == n_spheres

    def test_restarts_timer_in_vibration_mode(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        modes = [
            Mode(0, [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]]),
            Mode(1, [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]),
        ]
        structure = _make_structure(atoms, modes)
        cfg = Config.defaults()
        viewer = VispyViewer(structure, config=cfg, mode_type="animate")

        assert viewer.animation.timer is not None
        viewer.switch_mode(1)

        assert len(self.mock_timer.call_args_list) == 2

    def test_reuses_bond_transforms(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        modes = [
            Mode(0, [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]]),
            Mode(1, [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]], frequency=500.0, label="test"),
        ]
        structure = _make_structure(atoms, modes)
        cfg = Config.defaults()
        viewer = VispyViewer(structure, config=cfg, mode_type="static")

        assert len(viewer.scene.bonds.transforms) == 1
        old_tr = viewer.scene.bonds.transforms[0]
        viewer.switch_mode(1)

        assert viewer.scene.bonds.transforms[0] is old_tr


class TestAmplitudePeriodChanges:
    """Tests for amplitude and period changes via switch_mode."""

    def _make_viewer(self, mode_type="animate"):
        return VispyViewer(
            _make_structure(
                [Atom("H", [0.0, 0.0, 0.0])],
                [Mode(0, [[1.0, 0.0, 0.0]])],
            ),
            config=Config.defaults(),
            mode_type=mode_type,
        )

    def test_amplitude_applied_in_vibration_via_switch_mode(self):
        viewer = self._make_viewer("animate")
        viewer.amplitude = 0.5
        viewer.switch_mode(0)
        assert viewer.amplitude == 0.5
        assert hasattr(viewer.animation, "frames")

    def test_amplitude_applied_in_static_via_switch_mode(self):
        viewer = self._make_viewer("static")
        n_arrows_before = len(viewer.scene.overlay.visuals)
        viewer.amplitude = 0.5
        viewer.switch_mode(0)
        assert viewer.amplitude == 0.5
        assert len(viewer.scene.overlay.visuals) == n_arrows_before

    def test_period_applied_in_vibration_via_switch_mode(self):
        viewer = self._make_viewer("animate")
        viewer.period = 2.0
        viewer.switch_mode(0)
        assert viewer.period == 2.0
        assert hasattr(viewer.animation, "frames")

    def test_period_set_in_static_mode(self):
        viewer = self._make_viewer("static")
        viewer.period = 2.0
        viewer.switch_mode(0)
        assert viewer.period == 2.0


class TestSwitchModeDirect:
    """Tests for direct switch_mode calls."""

    def test_switch_mode_updates_index(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        modes = [
            Mode(0, [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]]),
            Mode(1, [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]),
        ]
        structure = _make_structure(atoms, modes)
        viewer = VispyViewer(structure, config=Config.defaults(), mode_type="static")

        viewer.switch_mode(1)
        assert viewer.mode_index == 1
