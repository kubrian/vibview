"""Tests for the parser format registry in parsers/__init__.py."""

import h5py
import numpy as np
import pytest

from vibview.parsers import PARSER_NAMES, parse


class TestRegistryContents:
    def test_native_registered(self):
        assert "native" in PARSER_NAMES

    def test_orca_registered(self):
        assert "orca" in PARSER_NAMES

    def test_registry_mapping(self, tmp_path):
        p = tmp_path / "test.h5"
        with h5py.File(p, "w") as f:
            g = f.create_group("atoms")
            g.create_dataset("symbols", data=np.array([b"H"]))
            g.create_dataset("positions", data=np.zeros((1, 3), dtype=np.float64))
            g = f.create_group("modes")
            g.create_dataset(
                "eigenvectors",
                data=np.array([[[1.0, 0.0, 0.0]]], dtype=np.float64),
            )
            g.create_dataset("frequencies", data=np.array([0.0], dtype=np.float64))
            g["frequencies"].attrs["units"] = "cm⁻¹"
        result = parse(p, "native", qpoint_index=0)
        assert result.source == str(p)

    def test_orca_dispatched_via_registry(self, tmp_path):
        content = """\
$atoms
3
 O     15.99900      0.0000000000    0.0000000000    0.0000000000
 H      1.00800      0.0000000000    1.4307929081    1.1070237687
 H      1.00800      0.0000000000   -1.4307929081    1.1070237687

$vibrational_frequencies
1
    0     1645.230000

$normal_modes
9 9
                    0
    0      0.000000
    1      0.707107
    2      0.000000
    3     -0.707107
    4      0.000000
    5      0.000000
    6      0.000000
    7      0.000000
    8      0.000000
"""
        p = tmp_path / "h2o.hess"
        p.write_text(content)
        result = parse(p, "orca", qpoint_index=0)
        data = result.data
        assert len(data.atoms) == 3
        assert len(data.modes) == 1
        assert data.modes[0].frequency == 1645.23


class TestRegistryErrors:
    def test_unknown_format(self, tmp_path):
        p = tmp_path / "foo.xyz"
        p.write_text("")
        with pytest.raises(ValueError, match="Unknown format"):
            parse(p, "nonexistent", qpoint_index=0)

    def test_unknown_format_message_lists_available(self, tmp_path):
        p = tmp_path / "foo.xyz"
        p.write_text("")
        with pytest.raises(ValueError, match="native.*orca"):
            parse(p, "bogus", qpoint_index=0)
