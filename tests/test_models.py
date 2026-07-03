import pytest

from vibview.models import Atom, Mode, VibData


def test_internal_format_validation():
    atoms = [Atom("O", [0, 0, 0]), Atom("O", [0, 0, 1.2])]
    modes = [Mode([[0, 0, -0.707], [0, 0, 0.707]], frequency=0.0)]

    VibData(atoms, modes, frequency_units="?")

    with pytest.raises(ValueError, match="Atoms list cannot be empty"):
        VibData([], modes, frequency_units="?")

    modes_invalid = [Mode([[0, 0, -0.707]], frequency=0.0)]
    with pytest.raises(ValueError, match="eigenvectors"):
        VibData(atoms, modes_invalid, frequency_units="?")

    # molecule invariant: qpoints and lattice must both be absent or both present
    with pytest.raises(ValueError, match="Molecular structures must have neither"):
        VibData(
            atoms,
            modes,
            frequency_units="?",
            lattice=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        )
    with pytest.raises(ValueError, match="Molecular structures must have neither"):
        VibData(atoms, modes, frequency_units="?", qpoints=[[0.0, 0.0, 0.0]])
    VibData(
        atoms,
        modes,
        frequency_units="?",
        qpoints=[[0.0, 0.0, 0.0]],
        lattice=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    )
