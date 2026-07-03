"""Tests for the storage module (in-place HDF5 mutations)."""

import h5py
import numpy as np

from tests.conftest import _make_crystal_h5, _make_molecular_h5
from vibview.models import Mode
from vibview.storage import update_labels


class TestUpdateLabels:
    def test_update_labels_molecular_writes_dataset(self, tmp_path):
        p = tmp_path / "mol.h5"
        _make_molecular_h5(p, n_atoms=1, n_modes=2)
        modes = [
            Mode([[1.0, 0.0, 0.0]], frequency=0.0, label="a"),
            Mode([[0.0, 1.0, 0.0]], frequency=0.0),
        ]
        update_labels(p, modes, qpoint_index=None)
        with h5py.File(p, "r") as f:
            ds = f["/modes/labels"][:]
            assert list(ds) == [b"a", b""]

    def test_update_labels_molecular_deletes_when_all_empty(self, tmp_path):
        p = tmp_path / "mol.h5"
        _make_molecular_h5(
            p,
            n_atoms=1,
            n_modes=2,
            labels=np.array(["a", "b"], dtype=h5py.string_dtype()),
        )
        modes = [
            Mode([[1.0, 0.0, 0.0]], frequency=0.0),
            Mode([[0.0, 1.0, 0.0]], frequency=0.0),
        ]
        update_labels(p, modes, qpoint_index=None)
        with h5py.File(p, "r") as f:
            assert "/modes/labels" not in f

    def test_update_labels_molecular_noop_on_empty_without_existing_dataset(
        self, tmp_path
    ):
        p = tmp_path / "mol.h5"
        _make_molecular_h5(p, n_atoms=1, n_modes=2)
        modes = [
            Mode([[1.0, 0.0, 0.0]], frequency=0.0),
            Mode([[0.0, 1.0, 0.0]], frequency=0.0),
        ]
        update_labels(p, modes, qpoint_index=None)
        with h5py.File(p, "r") as f:
            assert "/modes/labels" not in f

    def test_update_labels_crystal_updates_one_qpoint(self, tmp_path):
        p = tmp_path / "crystal.h5"
        existing = np.array([["x", "y"], ["", ""]], dtype=h5py.string_dtype())
        _make_crystal_h5(p, n_qpoints=2, n_bands=2, n_atoms=2, labels=existing)
        modes = [
            Mode([[1.0, 0.0, 0.0]], frequency=0.0, label="new_a"),
            Mode([[0.0, 1.0, 0.0]], frequency=0.0),
        ]
        update_labels(p, modes, qpoint_index=0)
        with h5py.File(p, "r") as f:
            ds = f["/modes/labels"][:]
            assert list(ds[0]) == [b"new_a", b""]
            assert list(ds[1]) == [b"", b""]

    def test_update_labels_crystal_deletes_when_all_empty(self, tmp_path):
        p = tmp_path / "crystal.h5"
        existing = np.array([["x", ""], ["", "y"]], dtype=h5py.string_dtype())
        _make_crystal_h5(p, n_qpoints=2, n_bands=2, n_atoms=2, labels=existing)
        modes = [
            Mode([[1.0, 0.0, 0.0]], frequency=0.0),
            Mode([[0.0, 1.0, 0.0]], frequency=0.0),
        ]
        update_labels(p, modes, qpoint_index=0)
        modes2 = [
            Mode([[1.0, 0.0, 0.0]], frequency=0.0),
            Mode([[0.0, 1.0, 0.0]], frequency=0.0),
        ]
        update_labels(p, modes2, qpoint_index=1)
        with h5py.File(p, "r") as f:
            assert "/modes/labels" not in f
