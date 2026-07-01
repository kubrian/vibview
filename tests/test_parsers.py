"""Tests for the native HDF5 parser and serializer."""

import h5py
import numpy as np
import pytest

from vibview.models import Atom, Mode, VibData
from vibview.parsers import make_qpoint_loader
from vibview.parsers.native import dump, parse, update_labels


def _make_h5(path, **overrides):
    n_atoms = overrides.get("n_atoms", 1)
    n_modes = overrides.get("n_modes", 1)
    ev = overrides.get(
        "eigenvectors",
        np.zeros((n_modes, n_atoms, 3), dtype=np.float16),
    )
    freq = overrides.get(
        "frequencies",
        np.full(n_modes, np.nan, dtype=np.float64),
    )
    symbols = overrides.get(
        "symbols",
        np.array(["H"] * n_atoms, dtype=h5py.string_dtype()),
    )
    positions = overrides.get(
        "positions",
        np.zeros((n_atoms, 3), dtype=np.float64),
    )

    with h5py.File(path, "w") as f:
        g = f.create_group("atoms")
        g.create_dataset("symbols", data=symbols)
        g.create_dataset("positions", data=positions)
        g = f.create_group("modes")
        g.create_dataset("eigenvectors", data=ev)
        g.create_dataset("frequencies", data=freq)
        if overrides.get("labels") is not None:
            g.create_dataset("labels", data=overrides["labels"])


class TestParseErrors:
    def test_unexpected_exception_not_caught(self, tmp_path, monkeypatch):
        p = tmp_path / "test.h5"
        p.write_text("irrelevant")

        def raise_typeerror(*args, **kwargs):
            raise TypeError("unexpected")

        monkeypatch.setattr("h5py.File", raise_typeerror)
        with pytest.raises(TypeError, match="unexpected"):
            parse(p)

    @pytest.mark.parametrize(
        ("setup_fn", "exc_type", "match"),
        [
            (None, OSError, "Unable to synchronously open file"),
            ("not-hdf5", OSError, "Unable to synchronously open file"),
            ("no-atoms", ValueError, "Missing /atoms datasets"),
            ("no-modes", ValueError, "Missing /modes/eigenvectors"),
        ],
    )
    def test_parse_error(self, tmp_path, setup_fn, exc_type, match):
        p = tmp_path / "test.h5"
        if setup_fn is None:
            p = "/nonexistent/path.h5"
        elif setup_fn == "not-hdf5":
            p.write_text("this is not an HDF5 file")
        elif setup_fn == "no-atoms":
            with h5py.File(p, "w") as f:
                pass
        elif setup_fn == "no-modes":
            with h5py.File(p, "w") as f:
                g = f.create_group("atoms")
                g.create_dataset("symbols", data=np.array([b"H"]))
                g.create_dataset("positions", data=np.zeros((1, 3), dtype=np.float64))
        with pytest.raises(exc_type, match=match):
            parse(p)


class TestParseSuccess:
    def test_valid_h5_single_atom_single_mode(self, tmp_path):
        p = tmp_path / "valid.h5"
        ev = np.array([[[1.0, 0.0, 0.0]]], dtype=np.float64)
        freq = np.array([100.0], dtype=np.float64)
        _make_h5(p, n_atoms=1, n_modes=1, eigenvectors=ev, frequencies=freq)
        result = parse(p)
        data = result.data
        assert len(data.atoms) == 1
        assert data.atoms[0].symbol == "H"
        assert data.modes[0].frequency == 100.0
        np.testing.assert_allclose(
            data.modes[0].eigenvectors, [[1.0, 0.0, 0.0]], atol=1e-6
        )

    def test_parse_multiple_atoms(self, tmp_path):
        p = tmp_path / "multi_atom.h5"
        symbols = np.array(["O", "H", "H"], dtype=h5py.string_dtype())
        positions = np.array(
            [[0.0, 0.0, 0.0], [0.7, 0.0, 0.5], [-0.7, 0.0, 0.5]], dtype=np.float64
        )
        ev = np.zeros((9, 3, 3), dtype=np.float64)
        ev[6, 0, 2] = 0.07
        ev[6, 1, 0] = 0.43
        ev[6, 1, 2] = -0.56
        ev[6, 2, 0] = -0.43
        freq = np.full(9, np.nan, dtype=np.float64)
        freq[6] = 1638.13
        _make_h5(
            p,
            symbols=symbols,
            positions=positions,
            n_modes=9,
            eigenvectors=ev,
            frequencies=freq,
        )
        result = parse(p)
        data = result.data
        assert len(data.atoms) == 3
        assert data.atoms[0].symbol == "O"
        assert data.modes[6].frequency == 1638.13
        assert data.modes[0].frequency is None
        assert data.modes[1].frequency is None

    def test_parse_with_labels(self, tmp_path):
        p = tmp_path / "labels.h5"
        ev = np.array([[[1.0, 0.0, 0.0]]], dtype=np.float64)
        labels = np.array(["stretch"], dtype=h5py.string_dtype())
        _make_h5(p, n_atoms=1, n_modes=1, eigenvectors=ev, labels=labels)
        result = parse(p)
        assert result.data.modes[0].label == "stretch"

    def test_parse_with_some_labels_none(self, tmp_path):
        p = tmp_path / "some_none.h5"
        ev = np.zeros((2, 1, 3), dtype=np.float64)
        labels = np.array(["stretch", ""], dtype=h5py.string_dtype())
        _make_h5(p, n_atoms=1, n_modes=2, eigenvectors=ev, labels=labels)
        result = parse(p)
        assert result.data.modes[0].label == "stretch"
        assert result.data.modes[1].label is None


class TestDump:
    def test_dump_roundtrip(self, tmp_path):
        data = VibData(
            atoms=[
                Atom("O", [0.0, 0.0, 0.0]),
                Atom("O", [0.0, 0.0, 1.2]),
            ],
            modes=[
                Mode(
                    [[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]],
                    frequency=1550.0,
                )
            ],
        )
        out = tmp_path / "roundtrip.h5"
        dump(data, out)
        result = parse(out)
        data = result.data
        assert len(data.atoms) == 2
        assert data.atoms[1].xyz == [0.0, 0.0, 1.2]
        assert data.modes[0].frequency == 1550.0
        assert data.modes[0].eigenvectors[1, 2] == pytest.approx(0.70710678, abs=1e-6)

    def test_dump_preserves_frequency_and_label(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[
                Mode(
                    [[1.0, 0.0, 0.0]],
                    frequency=100.0,
                    label="stretch",
                )
            ],
        )
        out = tmp_path / "labeled.h5"
        dump(data, out)
        result = parse(out)
        assert result.data.modes[0].frequency == 100.0
        assert result.data.modes[0].label == "stretch"

    def test_dump_omits_labels_dataset_when_all_none(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[Mode([[1.0, 0.0, 0.0]])],
        )
        out = tmp_path / "minimal.h5"
        dump(data, out)
        with h5py.File(out, "r") as f:
            assert "labels" not in f["/modes"]

    def test_dump_roundtrip_multiple_modes(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[
                Mode([[1.0, 0.0, 0.0]], frequency=100.0, label="mode_a"),
                Mode([[0.0, 1.0, 0.0]], frequency=200.0),
                Mode([[0.0, 0.0, 1.0]]),
            ],
        )
        out = tmp_path / "multi.h5"
        dump(data, out)
        result = parse(out)
        data = result.data
        assert len(data.modes) == 3
        assert data.modes[0].frequency == 100.0
        assert data.modes[0].label == "mode_a"
        assert data.modes[1].frequency == 200.0
        assert data.modes[1].label is None
        assert data.modes[2].frequency is None
        assert data.modes[2].label is None

    def test_dump_roundtrip_frequency_units(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[Mode([[1.0, 0.0, 0.0]], frequency=100.0)],
            frequency_units="cm⁻¹",
        )
        out = tmp_path / "units.h5"
        dump(data, out)
        result = parse(out)
        assert result.data.frequency_units == "cm⁻¹"
        with h5py.File(out, "r") as f:
            assert f["/modes/frequencies"].attrs["units"] == "cm⁻¹"

    def test_dump_roundtrip_frequency_units_override(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[Mode([[1.0, 0.0, 0.0]], frequency=100.0)],
        )
        out = tmp_path / "units_override.h5"
        dump(data, out, frequency_units="THz")
        result = parse(out)
        assert result.data.frequency_units == "THz"

    def test_dump_omits_units_attr_when_none(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[Mode([[1.0, 0.0, 0.0]], frequency=100.0)],
        )
        out = tmp_path / "no_units.h5"
        dump(data, out)
        with h5py.File(out, "r") as f:
            assert "units" not in f["/modes/frequencies"].attrs


def _make_crystal_h5(path, n_qpoints=2, n_bands=2, n_atoms=2, labels=None):
    ev = np.zeros((n_qpoints, n_bands, n_atoms, 3, 2), dtype=np.float16)
    for qi in range(n_qpoints):
        for bi in range(n_bands):
            ev[qi, bi, 0, 0, 0] = float(qi * n_bands + bi + 1)
    freq = np.full((n_qpoints, n_bands), np.nan, dtype=np.float64)
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
        if labels is not None:
            g.create_dataset("labels", data=labels)
        f.create_dataset("lattice", data=lattice)
        f.create_dataset("qpoints", data=qpoints)


class TestCrystalParse:
    def test_parse_crystal_basic(self, tmp_path):
        p = tmp_path / "crystal.h5"
        _make_crystal_h5(p, n_qpoints=2, n_bands=2, n_atoms=2)
        result = parse(p)
        data = result.data
        assert len(data.qpoints) == 2
        assert data.qpoints == [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]
        assert data.lattice is not None
        assert len(data.modes) == 2
        assert data.modes[0].frequency == 100.0
        assert data.modes[1].frequency is None
        assert data.modes[0].eigenvectors.shape == (2, 3)
        assert result.qpoint_loader is not None

    def test_parse_crystal_lazy_loading(self, tmp_path):
        p = tmp_path / "crystal_lazy.h5"
        _make_crystal_h5(p, n_qpoints=3, n_bands=2, n_atoms=2)
        result = parse(p)
        loader = result.qpoint_loader
        assert loader is not None
        modes_q1 = loader(1)
        assert len(modes_q1) == 2
        assert modes_q1[0].frequency is None
        assert modes_q1[1].frequency == 200.0
        assert modes_q1[0].eigenvectors.shape == (2, 3)
        modes_q2 = loader(2)
        assert len(modes_q2) == 2
        assert modes_q2[0].frequency is None
        assert modes_q2[1].frequency is None

    def test_parse_crystal_via_structure_switch_qpoint(self, tmp_path):
        from vibview.core import Structure

        p = tmp_path / "crystal_switch.h5"
        _make_crystal_h5(p, n_qpoints=2, n_bands=2, n_atoms=2)
        result = parse(p)
        structure = Structure(result.data, qpoint_loader=make_qpoint_loader(result))
        # modes are sorted by frequency ascending (None sorts after numeric)
        assert structure.modes[0].frequency == 100.0
        assert structure.modes[1].frequency is None
        assert structure.modes[0].eigenvectors.shape == (2, 3)
        structure.switch_qpoint(1)
        assert structure.modes[0].frequency == 200.0
        assert structure.modes[1].frequency is None
        assert structure.modes[0].eigenvectors.shape == (2, 3)
        structure.switch_qpoint(0)
        assert structure.modes[0].frequency == 100.0
        assert structure.modes[1].frequency is None

    def test_parse_crystal_with_labels(self, tmp_path):
        p = tmp_path / "crystal_labels.h5"
        labels = np.array([["label_a", ""], ["", "label_b"]], dtype=h5py.string_dtype())
        _make_crystal_h5(p, n_qpoints=2, n_bands=2, n_atoms=2, labels=labels)
        result = parse(p)
        data = result.data
        assert data.modes[0].label == "label_a"
        assert data.modes[1].label is None
        loader = make_qpoint_loader(result)
        modes_q1 = loader(1)
        assert modes_q1[0].label is None
        assert modes_q1[1].label == "label_b"

    def test_parse_crystal_molecular_data_has_no_lazy_loader(self, tmp_path):
        p = tmp_path / "molecular.h5"
        ev = np.array([[[1.0, 0.0, 0.0]]], dtype=np.float64)
        freq = np.array([100.0], dtype=np.float64)
        _make_h5(p, n_atoms=1, n_modes=1, eigenvectors=ev, frequencies=freq)
        result = parse(p)
        assert result.qpoint_loader is None
        assert result.data.qpoints is None


class TestCrystalDump:
    @pytest.mark.parametrize(
        ("n_qpoints", "labels"),
        [
            (2, None),
            (2, ["mode_a", "mode_b"]),
            (1, None),
        ],
    )
    def test_dump_crystal_roundtrip(self, tmp_path, n_qpoints, labels):
        mode0_kw = dict(frequency=100.0)
        if labels:
            mode0_kw["label"] = labels[0]
        data_modes = [Mode([[1.0, 0.0, 0.0]], **mode0_kw)]

        def lazy_loader(qi):
            kw = dict(frequency=100.0 * (qi + 1))
            if labels and qi != 0:
                kw["label"] = labels[qi]
            return [Mode([[1.0, 0.0, 0.0]], **kw)]

        qpoints = (
            [[0.0, 0.0, 0.0]] if n_qpoints == 1 else [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]
        )
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=data_modes,
            qpoints=qpoints,
            lattice=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
        )
        out = tmp_path / "crystal_out.h5"
        dump(data, out, qpoint_loader=lazy_loader)
        result = parse(out)
        assert len(result.data.qpoints) == n_qpoints
        loader = result.qpoint_loader
        for qi in range(n_qpoints):
            modes = loader(qi)
            assert modes[0].frequency == 100.0 * (qi + 1)
            if labels:
                assert modes[0].label == labels[qi]

    def test_dump_crystal_incomplete_raises(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[Mode([[1.0, 0.0, 0.0]])],
            qpoints=[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            lattice=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
        )
        out = tmp_path / "incomplete.h5"
        with pytest.raises(ValueError, match="Cannot access q-point 1"):
            dump(data, out)

    def test_dump_crystal_roundtrip_frequency_units(self, tmp_path):
        data = VibData(
            atoms=[Atom("H", [0.0, 0.0, 0.0])],
            modes=[Mode([[1.0, 0.0, 0.0]], frequency=100.0)],
            qpoints=[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            lattice=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
            frequency_units="THz",
        )
        out = tmp_path / "crystal_units.h5"
        dump(
            data,
            out,
            qpoint_loader=lambda qi: [
                Mode([[1.0, 0.0, 0.0]], frequency=100.0 * (qi + 1))
            ],
        )
        result = parse(out)
        assert result.data.frequency_units == "THz"
        with h5py.File(out, "r") as f:
            assert f["/modes/frequencies"].attrs["units"] == "THz"


class TestUpdateLabels:
    def test_update_labels_molecular_writes_dataset(self, tmp_path):
        p = tmp_path / "mol.h5"
        _make_h5(p, n_atoms=1, n_modes=2)
        modes = [Mode([[1.0, 0.0, 0.0]], label="a"), Mode([[0.0, 1.0, 0.0]])]
        update_labels(p, modes)
        with h5py.File(p, "r") as f:
            ds = f["/modes/labels"][:]
            assert list(ds) == [b"a", b""]

    def test_update_labels_molecular_deletes_when_all_empty(self, tmp_path):
        p = tmp_path / "mol.h5"
        _make_h5(
            p,
            n_atoms=1,
            n_modes=2,
            labels=np.array(["a", "b"], dtype=h5py.string_dtype()),
        )
        modes = [Mode([[1.0, 0.0, 0.0]]), Mode([[0.0, 1.0, 0.0]])]
        update_labels(p, modes)
        with h5py.File(p, "r") as f:
            assert "/modes/labels" not in f

    def test_update_labels_molecular_noop_on_empty_without_existing_dataset(
        self, tmp_path
    ):
        p = tmp_path / "mol.h5"
        _make_h5(p, n_atoms=1, n_modes=2)
        modes = [Mode([[1.0, 0.0, 0.0]]), Mode([[0.0, 1.0, 0.0]])]
        update_labels(p, modes)
        with h5py.File(p, "r") as f:
            assert "/modes/labels" not in f

    def test_update_labels_crystal_updates_one_qpoint(self, tmp_path):
        p = tmp_path / "crystal.h5"
        existing = np.array([["x", "y"], ["", ""]], dtype=h5py.string_dtype())
        _make_crystal_h5(p, n_qpoints=2, n_bands=2, n_atoms=2, labels=existing)
        modes = [Mode([[1.0, 0.0, 0.0]], label="new_a"), Mode([[0.0, 1.0, 0.0]])]
        update_labels(p, modes, qpoint_index=0)
        with h5py.File(p, "r") as f:
            ds = f["/modes/labels"][:]
            assert list(ds[0]) == [b"new_a", b""]
            assert list(ds[1]) == [b"", b""]

    def test_update_labels_crystal_deletes_when_all_empty(self, tmp_path):
        p = tmp_path / "crystal.h5"
        existing = np.array([["x", ""], ["", "y"]], dtype=h5py.string_dtype())
        _make_crystal_h5(p, n_qpoints=2, n_bands=2, n_atoms=2, labels=existing)
        modes = [Mode([[1.0, 0.0, 0.0]]), Mode([[0.0, 1.0, 0.0]])]
        update_labels(p, modes, qpoint_index=0)
        modes2 = [Mode([[1.0, 0.0, 0.0]]), Mode([[0.0, 1.0, 0.0]])]
        update_labels(p, modes2, qpoint_index=1)
        with h5py.File(p, "r") as f:
            assert "/modes/labels" not in f
