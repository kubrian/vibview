"""Tests for the ORCA Hessian file parser."""

import pytest
from pytest import approx

from vibview.parsers.orca import parse

HESS_H2O = """\
$atoms
3
 O     15.99900      0.0000000000    0.0000000000   -0.1223181927
 H      1.00800      1.4307929081    0.0000000000    1.0141177460
 H      1.00800     -1.4307929081    0.0000000000    1.0141177460

$vibrational_frequencies
9
    0        0.000000
    1        0.000000
    2        0.000000
    3        0.000000
    4        0.000000
    5        0.000000
    6     1645.230000
    7     3800.450000
    8     3900.670000

$normal_modes
9 9
                    0                  1                  2                  3                  4
    0      0.000000   0.000000   0.000000   0.000000   0.000000
    1      0.000000   0.000000   0.000000   0.000000   0.000000
    2      0.000000   0.000000   0.000000   0.000000   0.000000
    3      0.000000   0.000000   0.000000   0.000000   0.000000
    4      0.000000   0.000000   0.000000   0.000000   0.000000
    5      0.000000   0.000000   0.000000   0.000000   0.000000
    6      0.000000   0.000000   0.000000   0.000000   0.000000
    7      0.000000   0.000000   0.000000   0.000000   0.000000
    8      0.000000   0.000000   0.000000   0.000000   0.000000
                    5                  6                  7                  8
    0      0.000000   0.000000   0.000000  -0.069602
    1     -0.070222   0.070222   0.050492   0.000000
    2      0.000000   0.000000   0.000000   0.000000
    3     -0.432396  -0.432396  -0.581516   0.552359
    4      0.000000   0.000000   0.000000   0.000000
    5      0.557287   0.557287  -0.400704   0.438722
    6      0.432396   0.432396   0.581517   0.552359
    7      0.000000   0.000000   0.000000   0.000000
    8      0.557286   0.557286  -0.400704  -0.438722
"""

HESS_NO_GEOM = """\
$vibrational_frequencies
4
    0      100.000000

$normal_modes
3 3
                    0
    0      0.707107
    1      0.000000
    2      0.000000
"""

HESS_NO_FREQ = """\
$atoms
1
 O     16.00000      0.0000000000    0.0000000000    0.0000000000
"""

HESS_INCOMPLETE_MATRIX = """\
$atoms
2
 O     15.99900      0.0000000000    0.0000000000    0.0000000000
 H      1.00800      0.0000000000    0.7570000000    0.5860000000

$vibrational_frequencies
1
    0      100.000000

$normal_modes
6 6
                    0
    0      0.000000
    1      0.707107
    2     -0.707107
    3      0.000000
    4      0.000000
"""


class TestOrcaParseSuccess:
    def test_parse_water(self, tmp_path):
        p = tmp_path / "water.hess"
        p.write_text(HESS_H2O)
        result = parse(p)
        data = result.data
        assert len(data.atoms) == 3
        assert data.atoms[0].symbol == "O"
        assert data.atoms[0].xyz[0] == approx(0.0, abs=1e-10)
        assert data.atoms[0].xyz[1] == approx(0.0, abs=1e-10)
        assert data.atoms[0].xyz[2] == approx(-0.064728, abs=1e-10)
        assert data.atoms[1].symbol == "H"
        assert data.atoms[1].xyz[0] == approx(0.757143, abs=1e-10)
        assert data.atoms[1].xyz[1] == approx(0.0, abs=1e-10)
        assert data.atoms[1].xyz[2] == approx(0.536648, abs=1e-10)
        assert data.atoms[2].symbol == "H"
        assert data.atoms[2].xyz[0] == approx(-0.757143, abs=1e-10)
        assert data.atoms[2].xyz[1] == approx(0.0, abs=1e-10)
        assert data.atoms[2].xyz[2] == approx(0.536648, abs=1e-10)
        assert len(data.modes) == 9
        assert data.modes[0].frequency == 0.0
        assert data.modes[6].frequency == 1645.23
        assert data.modes[7].frequency == 3800.45
        assert data.modes[8].frequency == 3900.67
        assert len(data.modes[6].eigenvectors) == 3

    def test_negative_frequency(self, tmp_path):
        content = HESS_H2O.replace("1645.230000", "-100.500000")
        p = tmp_path / "imag.hess"
        p.write_text(content)
        result = parse(p)
        assert result.data.modes[6].frequency == -100.50

    def test_no_label_on_modes(self, tmp_path):
        p = tmp_path / "water.hess"
        p.write_text(HESS_H2O)
        result = parse(p)
        for mode in result.data.modes:
            assert mode.label is None


class TestOrcaParseErrors:
    def test_missing_geometry_section(self, tmp_path):
        p = tmp_path / "no_geom.hess"
        p.write_text(HESS_NO_GEOM)
        with pytest.raises(ValueError, match="No \\$atoms section"):
            parse(p)

    def test_missing_frequencies(self, tmp_path):
        p = tmp_path / "no_freq.hess"
        p.write_text(HESS_NO_FREQ)
        with pytest.raises(ValueError, match="No \\$vibrational_frequencies section"):
            parse(p)

    def test_missing_normal_modes(self, tmp_path):
        content = (
            HESS_NO_FREQ + "\n$vibrational_frequencies\n1\n    0      100.000000\n"
        )
        p = tmp_path / "no_modes.hess"
        p.write_text(content)
        with pytest.raises(ValueError, match="No \\$normal_modes section"):
            parse(p)

    def test_incomplete_normal_mode_matrix(self, tmp_path):
        p = tmp_path / "incomplete.hess"
        p.write_text(HESS_INCOMPLETE_MATRIX)
        with pytest.raises(ValueError, match="Incomplete normal mode matrix"):
            parse(p)

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.hess"
        p.write_text("")
        with pytest.raises(ValueError, match="No \\$atoms section"):
            parse(p)

    def test_malformed_frequency_line(self, tmp_path):
        content = """\
$atoms
1
 H      1.00800      0.0000000000    0.0000000000    0.0000000000

$vibrational_frequencies
2
    0      100.000000
    1      garbage

$normal_modes
3 3
                    0          1
    0      1.000000   0.000000
    1      0.000000   1.000000
    2     -0.707107   1.000000
"""
        p = tmp_path / "malformed.hess"
        p.write_text(content)
        with pytest.raises(ValueError, match="Malformed frequency line"):
            parse(p)

    def test_file_not_found(self, tmp_path):
        p = tmp_path / "nonexistent.hess"
        with pytest.raises(FileNotFoundError):
            parse(p)
