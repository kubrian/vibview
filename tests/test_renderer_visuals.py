"""Tests for vispy renderer visuals: spheres, tubes, arrows, wireframes, lattice."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.conftest import _make_structure, _make_structure_with_lattice, _make_viewer
from vibview.config import Config
from vibview.models import Atom, Mode
from vibview.renderers.vispy_renderer import VispyViewer

pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")


class TestVispyViewerStaticMode:
    def test_sphere_no_center_kwarg(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        mode = Mode(
            [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]],
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])

        cfg = Config.defaults()
        VispyViewer(structure, config=cfg, mode_type="static")

        sphere_calls = self.mock_sphere.call_args_list
        assert len(sphere_calls) == 2

        for call_args in sphere_calls:
            kwargs = call_args[1]
            assert "center" not in kwargs
            assert kwargs.get("radius") == pytest.approx(
                0.66 * cfg.rendering.radii_scale
            )
            assert kwargs.get("color") == pytest.approx(cfg.elements["O"].color.rgba)
            assert kwargs.get("method") == "ico"
            assert kwargs.get("subdivisions") == 2
            assert kwargs.get("shading") == cfg.rendering.effective_shading

        transform_calls = self.mock_st_transform.call_args_list
        assert len(transform_calls) == 2
        np.testing.assert_array_equal(
            transform_calls[0][1]["translate"], [0.0, 0.0, 0.0]
        )
        np.testing.assert_array_equal(
            transform_calls[1][1]["translate"], [0.0, 0.0, 1.2]
        )

    def test_arrow_positions(self):
        atoms = [Atom("O", [1.0, 0.0, 0.0]), Atom("O", [-1.0, 0.0, 0.0])]
        ev = [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]
        mode = Mode(
            ev,
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])

        amplitude = 2.0
        cfg = Config.defaults()
        cfg.animation.default_amplitude = amplitude
        VispyViewer(structure, config=cfg, mode_type="static")

        assert self.mock_tube.call_count == 5  # 3 axis + 2 arrow shafts
        assert self.mock_mesh.call_count == 5  # 3 axis + 2 arrow cones
        assert self.mock_create_cone.call_count == 5

        tube_calls = self.mock_tube.call_args_list
        # Last two tubes are arrow shafts (first 3 are axis indicators)
        tube0_points = tube_calls[-2][1]["points"]
        np.testing.assert_array_equal(tube0_points[0], [1.0, 0.0, 0.0])
        np.testing.assert_allclose(tube0_points[1], [1.35, 0.0, 0.0], atol=1e-6)

    def test_camera_center_is_centroid(self):
        atoms = [Atom("O", [2.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 4.0])]
        mode = Mode(
            [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]],
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])

        _make_viewer(structure, mode_type="static")

        _, call_kwargs = self.mock_camera.call_args_list[0]
        np.testing.assert_array_equal(call_kwargs["center"], [1.0, 0.0, 2.0])


class TestVispyViewerVibrationMode:
    """Tests for the vibration mode of VispyViewer."""

    def test_timer_created(self):
        structure = _make_structure(
            [Atom("N", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )

        cfg = Config.defaults()
        viewer = VispyViewer(structure, config=cfg, mode_type="animate")

        self.mock_timer.assert_called_once_with(
            interval=1 / cfg.animation.fps,
            connect=viewer.animation._tick,
            start=True,
        )

    def test_update_with_frames(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )

        viewer = _make_viewer(structure, mode_type="animate")
        assert len(viewer.scene.atoms.visuals) == 1
        assert viewer.scene.atoms.visuals[0].transform is not None

        viewer.scene.atoms.visuals = [MagicMock()]
        viewer.animation.frames = np.array([[[10.0, 0.0, 0.0]], [[20.0, 0.0, 0.0]]])
        viewer.animation.frame_idx = 0
        viewer.animation._merged_atom_meshes = []
        viewer.animation._merged_bond_meshes = []

        viewer.animation._tick(None)
        assert viewer.animation.frame_idx == 1
        np.testing.assert_array_equal(
            viewer.scene.atoms.visuals[0].transform.translate, [20.0, 0.0, 0.0]
        )

        viewer.animation._tick(None)
        assert viewer.animation.frame_idx == 0
        np.testing.assert_array_equal(
            viewer.scene.atoms.visuals[0].transform.translate, [10.0, 0.0, 0.0]
        )


class TestBonds:
    def test_bond_tube_created_static(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        mode = Mode(
            [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]],
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])

        cfg = Config.defaults()
        viewer = VispyViewer(structure, config=cfg, mode_type="static")

        assert hasattr(viewer.scene, "bonds")
        assert len(viewer.scene.bonds.visuals) == 1

        tube_call = self.mock_tube.call_args_list[0]
        np.testing.assert_array_equal(
            tube_call[1]["points"], [[0.0, 0.0, -0.5], [0.0, 0.0, 0.5]]
        )
        assert tube_call[1]["radius"] == cfg.rendering.bond_radius
        assert tube_call[1]["color"] == pytest.approx(cfg.rendering.bond_color.rgba)
        assert tube_call[1].get("shading") == cfg.rendering.effective_shading


class TestDiffMode:
    """Tests for diff mode wireframe visuals."""

    @pytest.fixture
    def oo_structure(self):
        return _make_structure(
            [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])],
            [
                Mode(
                    [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]],
                    frequency=0.0,
                )
            ],
        )

    def _get_wireframe_tube_calls(self, n_bonds):
        all_tube_calls = self.mock_tube.call_args_list
        return all_tube_calls[-2 * n_bonds :] if n_bonds > 0 else []

    def test_wireframe_tubes_created_for_each_bond(self, oo_structure):
        _make_viewer(oo_structure, mode_type="overlay")
        assert len(self._get_wireframe_tube_calls(n_bonds=1)) == 2

    def test_atoms_hidden_bonds_visible_in_overlay_mode(self, oo_structure):
        viewer = _make_viewer(oo_structure, mode_type="overlay")
        for s in viewer.scene.atoms.visuals:
            assert s.visible is False
        for b in viewer.scene.bonds.visuals:
            assert b.visible is True

    def test_wireframe_uses_translucent_blending_no_depth(self, oo_structure):
        _make_viewer(oo_structure, mode_type="overlay")
        for call in self.mock_tube.return_value.set_gl_state.call_args_list:
            kwargs = call[1]
            assert kwargs.get("preset") == "translucent"
            assert kwargs.get("depth_test") is False

    @pytest.mark.parametrize(
        ("idx", "alpha_key"),
        [(0, "eq_alpha"), (1, "disp_alpha")],
    )
    def test_wireframe_alpha(self, oo_structure, idx, alpha_key):
        cfg = Config.defaults()
        VispyViewer(oo_structure, config=cfg, mode_type="overlay")
        color = self._get_wireframe_tube_calls(n_bonds=1)[idx][1]["color"]
        assert len(color) == 4
        assert color[3] == pytest.approx(getattr(cfg.overlay, alpha_key))

    def test_equilibrium_wider_than_displaced(self, oo_structure):
        cfg = Config.defaults()
        VispyViewer(oo_structure, config=cfg, mode_type="overlay")
        wireframe_calls = self._get_wireframe_tube_calls(n_bonds=1)
        assert (
            wireframe_calls[0][1]["radius"]
            == cfg.rendering.bond_radius * cfg.overlay.eq_radius_multiplier
        )
        assert (
            wireframe_calls[1][1]["radius"]
            == cfg.rendering.bond_radius * cfg.overlay.disp_radius_multiplier
        )
        assert wireframe_calls[0][1]["radius"] > wireframe_calls[1][1]["radius"]

    def test_equilibrium_and_displaced_use_input_colors(self, oo_structure):
        cfg = Config.defaults()
        VispyViewer(oo_structure, config=cfg, mode_type="overlay")
        wireframe_calls = self._get_wireframe_tube_calls(n_bonds=1)
        assert wireframe_calls[0][1]["color"][:3] == pytest.approx(
            cfg.overlay.eq_color.rgb
        )
        assert wireframe_calls[1][1]["color"][:3] == pytest.approx(
            cfg.overlay.disp_color.rgb
        )

    def test_wireframe_multiple_bonds(self):
        atoms = [
            Atom("H", [0.0, 0.0, 0.0]),
            Atom("H", [1.0, 0.0, 0.0]),
            Atom("H", [0.5, 0.866, 0.0]),
        ]
        mode = Mode(
            [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])
        cfg = Config.defaults()
        VispyViewer(structure, config=cfg, mode_type="overlay")
        bonds = structure.detect_bonds(tolerance=0.4, config=cfg)
        assert len(self._get_wireframe_tube_calls(n_bonds=len(bonds))) == 2 * len(bonds)

    def test_diff_offset_gives_visible_separation(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        ev = [[0.0, 0.0, 0.5], [0.0, 0.0, -0.5]]
        structure = _make_structure(
            atoms,
            [
                Mode(
                    ev,
                    frequency=0.0,
                )
            ],
        )
        _make_viewer(structure, mode_type="overlay")
        wireframe_calls = self._get_wireframe_tube_calls(n_bonds=1)
        assert not np.array_equal(
            wireframe_calls[0][1]["points"], wireframe_calls[1][1]["points"]
        )

    def test_invalid_lattice_raises_error(self):
        """Ensure system fails loudly if lattice does not have 3 vectors."""
        lattice = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        structure = _make_structure_with_lattice(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
            lattice,
        )

        with pytest.raises(
            ValueError, match="Invalid lattice: expected 0 or 3 vectors"
        ):
            _make_viewer(structure, mode_type="static")

    def test_no_bonds_diff_mode_no_crash(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        _make_viewer(structure, mode_type="overlay")
        assert len(self.mock_tube.call_args_list) == 3  # axis indicators only


class TestUnknownElementInRenderer:
    """Visuals built for atoms with unknown element symbols."""

    def test_unknown_element_uses_fallback(self):
        atoms = [Atom("Xx", [0.0, 0.0, 0.0])]
        structure = _make_structure(
            atoms,
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        cfg = Config.defaults()
        VispyViewer(structure, config=cfg, mode_type="static")
        sphere_calls = self.mock_sphere.call_args_list
        assert sphere_calls[0][1]["color"] == pytest.approx(
            cfg.rendering.atom_color.rgba
        )
        assert sphere_calls[0][1]["radius"] == pytest.approx(
            cfg.rendering.atom_radius * cfg.rendering.radii_scale
        )


class TestBondTransforms:
    """Edge cases in SceneBuilder.update_bond_transforms."""

    def test_bond_along_positive_z(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        mode = Mode(
            [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]],
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])
        viewer = _make_viewer(structure, mode_type="static")

        assert len(viewer.scene.bonds.transforms) == 1
        tr = viewer.scene.bonds.transforms[0]
        tr.translate.assert_called_once()
        tr.scale.assert_not_called()
        assert tr.rotate.call_count == 0

    @pytest.mark.parametrize(
        ("atom_positions", "expected_rotate"),
        [
            ([[0.0, 0.0, 0.0], [0.0, 0.0, -1.2]], (180.0, (1.0, 0.0, 0.0))),
            ([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], (90.0, (0.0, 1.0, 0.0))),
        ],
    )
    def test_bond_rotation(self, atom_positions, expected_rotate):
        atoms = [
            Atom("O", atom_positions[0]),
            Atom("O", atom_positions[1]),
        ]
        mode = Mode(
            [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])
        viewer = _make_viewer(structure, mode_type="static")

        tr = viewer.scene.bonds.transforms[0]
        tr.translate.assert_called_once()
        tr.scale.assert_not_called()

    def test_zero_length_bond(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 0.0])]
        mode = Mode(
            [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
            frequency=0.0,
        )
        structure = _make_structure(atoms, [mode])
        viewer = _make_viewer(structure, mode_type="static")

        assert len(viewer.scene.bonds.transforms) == 1
        tr = viewer.scene.bonds.transforms[0]
        tr.translate.assert_called_once()
        tr.scale.assert_not_called()


class TestFramesPerCycle:
    """Tests for the frames_per_cycle property."""

    @pytest.mark.parametrize(
        ("fps", "period", "expected"),
        [
            (60, 1.0, 60),
            (30, 2.0, 60),
        ],
    )
    def test_frames_per_cycle(self, fps, period, expected):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        cfg = Config.defaults()
        cfg.animation.fps = fps
        cfg.animation.period = period
        viewer = VispyViewer(structure, config=cfg, mode_type="static")
        assert viewer.animation.frames_per_cycle == expected

    def test_frames_per_cycle_minimum_two(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        cfg = Config.defaults()
        cfg.animation.fps = 1
        cfg.animation.period = 0.1
        viewer = VispyViewer(structure, config=cfg, mode_type="static")
        assert viewer.animation.frames_per_cycle >= 2


LATTICE = [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]]


class TestLattice:
    """Tests for unit-cell lattice box rendering."""

    @pytest.fixture
    def lattice_struct(self):
        return _make_structure_with_lattice(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
            LATTICE,
        )

    def test_mesh_created_when_lattice_present(self, lattice_struct):
        viewer = _make_viewer(lattice_struct, mode_type="static")
        assert len(viewer.scene.lattice.visuals) == 1

    def test_not_created_without_lattice(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        viewer = _make_viewer(structure, mode_type="static")
        assert len(viewer.scene.lattice.visuals) == 0

    def test_configures_mesh_properties(self, lattice_struct):
        cfg = Config.defaults()
        cfg.lattice.width = 0.05
        cfg.lattice.alpha = 0.5
        viewer = VispyViewer(lattice_struct, config=cfg, mode_type="static")

        mesh = viewer.scene.lattice.visuals[0]
        assert mesh.meshdata is not None
        color = mesh.color
        assert len(color) == 4
        assert color[3] == cfg.lattice.alpha

    def test_persists_across_mode_switch(self):
        modes = [
            Mode(
                [[1.0, 0.0, 0.0]],
                frequency=0.0,
            ),
            Mode(
                [[-1.0, 0.0, 0.0]],
                frequency=0.0,
            ),
        ]
        structure = _make_structure_with_lattice(
            [Atom("H", [1.0, 0.0, 0.0])], modes, LATTICE
        )
        viewer = _make_viewer(structure, mode_type="static")
        viewer.switch_mode(1)
        assert len(viewer.scene.lattice.visuals) == 1


class TestAxisIndicators:
    def test_cartesian_axes_created(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(
            atoms,
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        viewer = _make_viewer(structure, mode_type="static")
        assert len(viewer.camera.axis_visuals) == 6  # 3 arrows * (tube + cone)

    def test_axis_indicators_with_lattice(self):
        structure = _make_structure_with_lattice(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
            LATTICE,
        )
        viewer = _make_viewer(structure, mode_type="static")
        assert len(viewer.camera.axis_visuals) == 6  # 3 lattice arrows * (tube + cone)

    def test_persists_across_mode_switch(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                ),
                Mode(
                    [[-1.0, 0.0, 0.0]],
                    frequency=0.0,
                ),
            ],
        )
        viewer = _make_viewer(structure, mode_type="static")
        assert len(viewer.camera.axis_visuals) == 6
        viewer.switch_mode(1)
        assert len(viewer.camera.axis_visuals) == 6

    def test_axes_hidden_when_show_axis_false(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(
            atoms,
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        cfg = Config.defaults()
        cfg.display.show_axis = False
        viewer = VispyViewer(structure, config=cfg, mode_type="static")
        assert len(viewer.camera.axis_visuals) == 0
        assert len(viewer.camera.axis_labels) == 0


class TestCameraInteraction:
    def test_axis_sync_events_connected(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(
            atoms,
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        viewer = _make_viewer(structure, mode_type="static")
        viewer.camera.view.camera.events.mouse_move.connect.assert_called_once_with(
            viewer.camera.sync_axis_camera
        )
        viewer.camera.view.camera.events.mouse_wheel.connect.assert_called_once_with(
            viewer.camera.sync_axis_camera
        )
        viewer.camera.canvas.events.draw.connect.assert_any_call(
            viewer.camera.sync_axis_camera
        )

    def test_camera_reset(self):
        atoms = [Atom("H", [0.0, 0.0, 0.0])]
        structure = _make_structure(
            atoms,
            [
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=0.0,
                )
            ],
        )
        viewer = _make_viewer(structure, mode_type="static")
        viewer.camera.set_initial_state(
            center=np.array([1.0, 2.0, 3.0]),
            distance=15.0,
            quaternion=viewer.camera.view.camera.quaternion.copy(),
        )
        viewer.camera.view.camera.center = (10.0, 20.0, 30.0)
        viewer.camera.view.camera.distance = 999.0

        viewer.camera.reset_camera()
        np.testing.assert_array_equal(viewer.camera.view.camera.center, [1.0, 2.0, 3.0])
        assert viewer.camera.view.camera.distance == 15.0
        assert viewer.camera.canvas.update.called
        assert viewer.camera.view.camera.view_changed.called
