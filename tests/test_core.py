import h5py
import numpy as np
import pytest

from tests.conftest import _make_structure
from vibview.config import Config
from vibview.core import (
    Structure,
    _cell_offsets,
    generate_frames,
)
from vibview.models import Atom, Mode
from vibview.parsers import parse as parse_file


def _gen(structure, mode_index, **kwargs):
    defaults = dict(amplitude=1.0, frames=1, cycles=1, supercell=None)
    defaults.update(kwargs)
    return generate_frames(structure, mode_index, **defaults)


class TestGetMode:
    def test_get_mode_by_position(self):
        structure = _make_structure(
            [Atom("O", [0, 0, 0]), Atom("O", [0, 0, 1.2])],
            [Mode([[0, 0, -0.707], [0, 0, 0.707]], frequency=0.0)],
        )
        mode = structure.get_mode(0)
        assert mode is not None

    def test_invalid_position_raises(self):
        structure = _make_structure(
            [Atom("O", [0, 0, 0]), Atom("O", [0, 0, 1.2])],
            [Mode([[0, 0, -0.707], [0, 0, 0.707]], frequency=0.0)],
        )
        with pytest.raises(IndexError):
            structure.get_mode(5)


class TestDetectBonds:
    _cfg = Config.defaults()

    def test_unknown_element_raises_key_error(self):
        atoms = [Atom("Xx", [0.0, 0.0, 0.0]), Atom("Xx", [0.0, 0.0, 1.5])]
        structure = _make_structure(
            atoms, [Mode([[1, 0, 0], [-1, 0, 0]], frequency=0.0)]
        )
        with pytest.raises(KeyError, match="Xx"):
            structure.detect_bonds(tolerance=0.4, config=self._cfg)

    def test_mixed_known_unknown_elements_raises_key_error(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("Xx", [0.0, 0.0, 1.5])]
        structure = _make_structure(
            atoms, [Mode([[1, 0, 0], [-1, 0, 0]], frequency=0.0)]
        )
        with pytest.raises(KeyError, match="Xx"):
            structure.detect_bonds(tolerance=0.4, config=self._cfg)

    def test_bond_detected_known_structure(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
        structure = _make_structure(
            atoms,
            [Mode([[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]], frequency=0.0)],
        )
        bonds = structure.detect_bonds(tolerance=0.4, config=self._cfg)
        assert len(bonds) == 1
        assert abs(bonds[0][2] - 1.2) < 1e-6

    def test_no_bond_far_atoms(self):
        atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 5.0])]
        structure = _make_structure(
            atoms,
            [Mode([[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]], frequency=0.0)],
        )
        bonds = structure.detect_bonds(tolerance=0.4, config=self._cfg)
        assert len(bonds) == 0

    def test_bond_with_tolerance(self):
        atoms = [Atom("C", [0.0, 0.0, 0.0]), Atom("C", [0.0, 0.0, 2.0])]
        structure = _make_structure(
            atoms,
            [Mode([[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]], frequency=0.0)],
        )
        bonds = structure.detect_bonds(tolerance=0.4, config=self._cfg)
        assert len(bonds) == 0
        bonds = structure.detect_bonds(tolerance=0.5, config=self._cfg)
        assert len(bonds) == 1

    def test_no_bonds_single_atom(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        bonds = structure.detect_bonds(tolerance=0.4, config=self._cfg)
        assert bonds == []


class TestGenerateFrames:
    def test_shape_and_values(self):
        structure = _make_structure(
            [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])],
            [Mode([[0, 0, -0.707], [0, 0, 0.707]], frequency=0.0)],
        )
        frames = _gen(structure, 0, frames=4)
        assert frames.shape == (4, 2, 3)
        # t=0 → cos(0)=1 → max displacement
        assert np.allclose(frames[0], [[0, 0, -1.0], [0, 0, 2.2]], atol=1e-5)
        # t=0.5 → cos(π)=-1 → opposite max displacement
        assert np.allclose(frames[2], [[0, 0, 1.0], [0, 0, 0.2]], atol=1e-5)

    def test_single_frame(self):
        structure = _make_structure(
            [Atom("H", [1.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        frames = _gen(structure, 0, amplitude=0.5)
        assert frames.shape == (1, 1, 3)
        # t=0 → cos(0)=1 → max displacement
        assert np.allclose(frames[0], [[1.5, 0.0, 0.0]])

    def test_cycles_multiplies_frame_count(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        single = _gen(structure, 0, frames=4)
        multi = _gen(structure, 0, frames=4, cycles=3)
        assert single.shape == (4, 1, 3)
        assert multi.shape == (12, 1, 3)
        # each cycle ends at the same position
        assert np.allclose(multi[0], multi[4])  # start of cycle 1 vs start of cycle 2
        assert np.allclose(multi[4], multi[8])  # start of cycle 2 vs start of cycle 3

    def test_supercell_expansion(self):
        """Supercell frames match expected per-cell displacements at q=Γ."""
        structure = _make_structure(
            [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])],
            [Mode([[0, 0, -0.707], [0, 0, 0.707]], frequency=0.0)],
        )
        structure.data.lattice = [[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]]
        structure.data.qpoints = [[0.0, 0.0, 0.0]]

        frames = _gen(structure, 0, frames=4, supercell=(2, 1, 1))
        assert frames.shape == (4, 4, 3)  # 4 frames, 2 cells * 2 atoms = 4
        # At q=(0,0,0) and t=0, cell 0 and cell 1 have identical displacements
        # Cell 1: atoms at [0,0,0], [0,0,1.2]; Cell 2: atoms at [3,0,0], [3,0,1.2]
        np.testing.assert_allclose(frames[0, 0], [0, 0, -1.0], atol=1e-5)
        np.testing.assert_allclose(frames[0, 1], [0, 0, 2.2], atol=1e-5)
        np.testing.assert_allclose(frames[0, 2], [3, 0, -1.0], atol=1e-5)
        np.testing.assert_allclose(frames[0, 3], [3, 0, 2.2], atol=1e-5)

    def test_supercell_nonzero_q_bloch_phase(self):
        """At q=(0.5,0,0), 2×1×1 supercell: cell 0 and cell 1 oppose at t=0."""
        structure = _make_structure(
            [Atom("O", [0.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        structure.data.lattice = [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]]
        structure.data.qpoints = [[0.5, 0.0, 0.0]]

        frames = _gen(structure, 0, frames=4, supercell=(2, 1, 1))
        assert frames.shape == (4, 2, 3)
        # cell 0 displaced +x, cell 1 displaced -x
        cell0_disp = frames[0, 0] - [0, 0, 0]
        cell1_disp = frames[0, 1] - [4, 0, 0]
        np.testing.assert_allclose(cell0_disp, -cell1_disp, atol=1e-5)

    def test_supercell_no_lattice_raises(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        with pytest.raises(ValueError, match="lattice vectors"):
            _gen(structure, 0, supercell=(2, 1, 1))

    def test_single_frame_displacement_amplitude(self):
        """frames=1 at t=0 yields displacement vectors with max norm ≈ amplitude."""
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0]), Atom("H", [1.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0], [-0.5, 0.0, 0.0]], frequency=0.0)],
        )
        frames = _gen(structure, 0, amplitude=0.5)
        disps = frames[0] - structure.xyz
        assert disps.shape == (2, 3)
        max_norm = np.linalg.norm(disps, axis=1).max()
        assert max_norm == pytest.approx(0.5, abs=1e-6)

    def test_single_frame_zero_amplitude(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        frames = _gen(structure, 0, amplitude=0.0)
        np.testing.assert_allclose(frames[0], structure.xyz)

    def test_single_frame_single_atom(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        frames = _gen(structure, 0, amplitude=2.0)
        disps = frames[0] - structure.xyz
        assert disps[0, 0] == pytest.approx(2.0, abs=1e-6)

    def test_single_frame_all_zero_eigenvectors(self):
        structure = _make_structure(
            [Atom("H", [0.0, 0.0, 0.0]), Atom("H", [1.0, 0.0, 0.0])],
            [Mode([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], frequency=0.0)],
        )
        frames = _gen(structure, 0)
        np.testing.assert_allclose(frames[0], structure.xyz)

    def test_supercell_displacement_amplitude(self):
        """Supercell displacement max norm ≈ amplitude at t=0."""
        structure = _make_structure(
            [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])],
            [Mode([[0, 0, -0.707], [0, 0, 0.707]], frequency=0.0)],
        )
        structure.data.lattice = [[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]]
        structure.data.qpoints = [[0.0, 0.0, 0.0]]

        lattice = np.array(structure.data.lattice, dtype=np.float64)
        cell_offsets = _cell_offsets((2, 1, 1))
        cell_offsets_cart = cell_offsets @ lattice
        xyz = np.asarray(structure.xyz, dtype=np.float64)
        eq_xyz = (xyz[np.newaxis, :, :] + cell_offsets_cart[:, np.newaxis, :]).reshape(
            -1, 3
        )

        frames = _gen(structure, 0, supercell=(2, 1, 1))
        disps = frames[0] - eq_xyz
        assert disps.shape == (4, 3)
        # At q=Γ, all cells have identical displacement
        np.testing.assert_allclose(disps[0], disps[2], atol=1e-6)
        np.testing.assert_allclose(disps[1], disps[3], atol=1e-6)

    def test_supercell_nonzero_q_displacement(self):
        """Supercell displacement with non-zero q shows Bloch phase."""
        structure = _make_structure(
            [Atom("O", [0.0, 0.0, 0.0])],
            [Mode([[1.0, 0.0, 0.0]], frequency=0.0)],
        )
        structure.data.lattice = [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]]
        structure.data.qpoints = [[0.5, 0.0, 0.0]]

        lattice = np.array(structure.data.lattice, dtype=np.float64)
        cell_offsets = _cell_offsets((2, 1, 1))
        cell_offsets_cart = cell_offsets @ lattice
        xyz = np.asarray(structure.xyz, dtype=np.float64)
        eq_xyz = (xyz[np.newaxis, :, :] + cell_offsets_cart[:, np.newaxis, :]).reshape(
            -1, 3
        )

        frames = _gen(structure, 0, supercell=(2, 1, 1))
        disps = frames[0] - eq_xyz
        assert disps.shape == (2, 3)
        # Cell 0: exp(i·0) = 1 → displacement along +x
        # Cell 1: exp(i·π) = -1 → displacement along -x
        np.testing.assert_allclose(disps[0], [1.0, 0.0, 0.0], atol=1e-5)
        np.testing.assert_allclose(disps[1], [-1.0, 0.0, 0.0], atol=1e-5)


class TestFromFile:
    def test_from_file_native(self, tmp_path):
        p = tmp_path / "structure.h5"
        with h5py.File(p, "w") as f:
            g = f.create_group("atoms")
            g.create_dataset("symbols", data=np.array([b"H"]))
            g.create_dataset("positions", data=np.zeros((1, 3), dtype=np.float64))
            g = f.create_group("modes")
            g.create_dataset(
                "eigenvectors",
                data=np.array([[[1.0, 0.0, 0.0]]], dtype=np.float64),
            )
            g.create_dataset("frequencies", data=np.array([100.0], dtype=np.float64))
            g["frequencies"].attrs["units"] = "cm⁻¹"
        structure = Structure(
            parse_file(p, "native", qpoint_index=0).data, qpoint_loader=None
        )
        assert len(structure.atoms) == 1
        assert structure.atoms[0].symbol == "H"


class TestSupercellHelpers:
    def test_cell_offsets(self):
        offsets = _cell_offsets((2, 1, 1))
        assert offsets.shape == (2, 3)
        np.testing.assert_array_equal(offsets, [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])

        offsets3 = _cell_offsets((2, 2, 1))
        assert offsets3.shape == (4, 3)
        np.testing.assert_array_equal(
            offsets3,
            [
                [0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
            ],
        )
