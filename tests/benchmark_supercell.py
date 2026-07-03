"""Benchmarks for supercell rendering performance.

Measures the time to build visuals across supercell sizes.
Run with: pixi run pytest tests/benchmark_supercell.py --benchmark-only
"""

import pytest
from conftest import _make_structure_with_lattice, _make_viewer

from vibview.config import Config
from vibview.core import _cell_offsets
from vibview.models import Atom, Mode

pytestmark = pytest.mark.usefixtures("_mock_qt_window", "_patch_vispy")


LATTICE = [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]]


@pytest.fixture(
    params=[
        (1, 1, 1),
        (2, 2, 2),
        (3, 3, 3),
        (5, 5, 5),
    ],
    ids=["1x1x1", "2x2x2", "3x3x3", "5x5x5"],
)
def supercell(request):
    return request.param


@pytest.fixture
def benchmark_structure():
    """O2 molecule (2 atoms) with lattice for supercell expansion."""
    atoms = [Atom("O", [0.0, 0.0, 0.0]), Atom("O", [0.0, 0.0, 1.2])]
    mode = Mode([[0.0, 0.0, -0.707], [0.0, 0.0, 0.707]], frequency=0.0, label=None)
    return _make_structure_with_lattice(atoms, [mode], LATTICE)


class TestSupercellBenchmark:
    """Measure supercell-related operations."""

    def test_ensure_supercell_time(self, benchmark_structure, supercell, benchmark):
        def setup():
            v = _make_viewer(
                benchmark_structure,
                mode_type="static",
                supercell=(1, 1, 1),
            )
            v.scene.supercell = supercell
            return (v,), {}

        def run(v):
            v.scene.ensure_supercell()

        benchmark.pedantic(run, setup=setup, rounds=8)

    def test_build_base_visuals_time(self, benchmark_structure, supercell, benchmark):
        viewer = _make_viewer(
            benchmark_structure,
            mode_type="static",
            supercell=supercell,
        )

        @benchmark
        def run():
            viewer.scene.build_base()

    def test_supercell_cell_offsets_time(self, supercell, benchmark):
        benchmark(_cell_offsets, supercell)

    def test_bond_count(self, benchmark_structure, supercell):
        from vibview.renderers.vispy_renderer import VispyViewer

        config = Config.defaults()
        config.rendering.radii_scale = 1.0
        viewer = VispyViewer(
            benchmark_structure,
            config=config,
            mode_type="static",
            supercell=supercell,
        )
        n_cells = supercell[0] * supercell[1] * supercell[2]
        n_basis_bonds = len(
            benchmark_structure.detect_bonds(tolerance=config.rendering.bond_tolerance)
        )
        assert len(viewer.scene.bonds.indices) == n_cells * n_basis_bonds
