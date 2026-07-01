"""Tests for the self-contained phonopy YAML parser."""

import math
from functools import partial

import numpy as np
import pytest

from vibview.core import Structure
from vibview.models import Atom, Mode, VibData
from vibview.parsers import make_qpoint_loader
from vibview.parsers.phonopy import parse as _parse

parse = partial(_parse, qpoint_index=0)

_O_SQRT2 = 1.0 / math.sqrt(2)

PHONOPY_YAML = f"""\
nqpoint: 2
natom: 2
lattice:
- [ 3.0, 0.0, 0.0 ]
- [ 0.0, 3.0, 0.0 ]
- [ 0.0, 0.0, 3.0 ]
points:
- symbol: O
  coordinates: [ 0.0, 0.0, 0.0 ]
  mass: 15.9994
- symbol: H
  coordinates: [ 0.5, 0.5, 0.5 ]
  mass: 1.00794
phonon:
- q-position: [ 0.0, 0.0, 0.0 ]
  distance: 0.0
  band:
  - # 1
    frequency: 0.0
    eigenvector:
    - [ [{_O_SQRT2}, 0.0], [0.0, 0.0], [0.0, 0.0] ]
    - [ [{_O_SQRT2}, 0.0], [0.0, 0.0], [0.0, 0.0] ]
  - # 2
    frequency: 10.0
    eigenvector:
    - [ [{_O_SQRT2}, 0.0], [0.0, 0.0], [0.0, 0.0] ]
    - [ [{-_O_SQRT2}, 0.0], [0.0, 0.0], [0.0, 0.0] ]
- q-position: [ 0.5, 0.0, 0.0 ]
  distance: 0.5
  band:
  - # 1
    frequency: 5.0
    eigenvector:
    - [ [1.0, 0.0], [0.0, 0.0], [0.0, 0.0] ]
    - [ [0.0, 0.0], [1.0, 0.0], [0.0, 0.0] ]
  - # 2
    frequency: 15.0
    eigenvector:
    - [ [0.0, 0.0], [1.0, 0.0], [0.0, 0.0] ]
    - [ [1.0, 0.0], [0.0, 0.0], [0.0, 0.0] ]
"""


def _norm(vec):
    arr = np.asarray(vec, dtype=np.complex64)
    return float(np.linalg.norm(arr.ravel()))


def _write_yaml(tmp_path, text: str):
    p = tmp_path / "band.yaml"
    p.write_text(text)
    return p


class TestPhonopyParserSuccess:
    def test_parse_multi_qpoint(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, PHONOPY_YAML)
        result = parse(yaml_path)
        data = result.data

        assert len(data.atoms) == 2
        assert data.atoms[0].symbol == "O"
        assert data.atoms[1].symbol == "H"

        assert len(data.qpoints) == 2
        assert data.qpoints[0] == [0.0, 0.0, 0.0]
        assert data.qpoints[1] == [0.5, 0.0, 0.0]

        assert result.source == str(yaml_path)
        assert make_qpoint_loader(result) is not None

        assert len(data.modes) == 2
        assert data.modes[0].frequency == 0.0
        assert data.modes[1].frequency == 10.0

        assert data.lattice == [
            [3.0, 0.0, 0.0],
            [0.0, 3.0, 0.0],
            [0.0, 0.0, 3.0],
        ]

    def test_qpoint_index_selects_correct_modes(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, PHONOPY_YAML)
        result = parse(yaml_path, qpoint_index=1)
        data = result.data

        assert len(data.modes) == 2
        assert data.modes[0].frequency == 5.0
        assert data.modes[1].frequency == 15.0

    def test_atom_mass_from_yaml(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, PHONOPY_YAML)
        result = parse(yaml_path)
        ev = result.data.modes[0].eigenvectors
        assert _norm(ev) == pytest.approx(1.0, abs=1e-10)

    def test_lazy_loading_returns_correct_modes_for_each_qpoint(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, PHONOPY_YAML)
        result = parse(yaml_path)
        loader = result.qpoint_loader

        modes_q0 = loader(0)
        assert len(modes_q0) == 2
        assert modes_q0[0].frequency == 0.0
        assert modes_q0[1].frequency == 10.0

        modes_q1 = loader(1)
        assert len(modes_q1) == 2
        assert modes_q1[0].frequency == 5.0
        assert modes_q1[1].frequency == 15.0

    def test_structure_switch_qpoint(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, PHONOPY_YAML)
        result = parse(yaml_path)
        structure = Structure(result.data, qpoint_loader=make_qpoint_loader(result))
        assert structure.modes[0].frequency == 0.0
        assert structure.modes[1].frequency == 10.0
        structure.switch_qpoint(1)
        assert structure.modes[0].frequency == 5.0
        assert structure.modes[1].frequency == 15.0
        structure.switch_qpoint(0)
        assert structure.modes[0].frequency == 0.0
        assert structure.modes[1].frequency == 10.0

    @pytest.mark.parametrize(
        ("qpoint_index", "match"),
        [(5, "qpoint_index 5 out of range"), (-1, "qpoint_index -1 out of range")],
    )
    def test_out_of_range_qpoint_index(self, tmp_path, qpoint_index, match):
        yaml_path = _write_yaml(tmp_path, PHONOPY_YAML)
        with pytest.raises(ValueError, match=match):
            parse(yaml_path, qpoint_index=qpoint_index)


def test_switch_qpoint_on_non_qpoint_data_errors():
    data = VibData(
        atoms=[Atom("O", [0.0, 0.0, 0.0])],
        modes=[Mode([[1.0, 0.0, 0.0]])],
    )
    structure = Structure(data)
    with pytest.raises(ValueError, match="No q-point data available"):
        structure.switch_qpoint(0)


class TestPhonopyParseErrors:
    def test_missing_yaml(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Phonopy YAML file not found"):
            parse(tmp_path / "nonexistent.yaml")

    def test_not_a_dict(self, tmp_path):
        p = _write_yaml(tmp_path, "- just\n- a\n- list\n")
        with pytest.raises(ValueError, match="No 'phonon' section found"):
            parse(p)

    def test_no_points(self, tmp_path):
        p = _write_yaml(tmp_path, "phonon: []\n")
        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            parse(p)

    def test_no_lattice(self, tmp_path):
        p = _write_yaml(
            tmp_path,
            "points:\n- {symbol: O, coordinates: [0,0,0]}\nphonon: []\n",
        )
        with pytest.raises(ValueError, match="No 'lattice' section"):
            parse(p)

    def test_no_phonon(self, tmp_path):
        p = _write_yaml(
            tmp_path,
            "lattice:\n- [1,0,0]\n- [0,1,0]\n- [0,0,1]\npoints:\n- symbol: O\n  coordinates: [0,0,0]\n",
        )
        with pytest.raises(ValueError, match="No 'phonon' section"):
            parse(p)
