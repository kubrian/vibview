import pytest

from vibview.models import Atom, Mode, VibData


def test_internal_format_validation():
    atoms = [Atom("O", [0, 0, 0]), Atom("O", [0, 0, 1.2])]
    modes = [Mode(0, [[0, 0, -0.707], [0, 0, 0.707]])]

    VibData(atoms, modes)

    with pytest.raises(ValueError, match="Atoms list cannot be empty"):
        VibData([], modes)

    modes_invalid = [Mode(0, [[0, 0, -0.707]])]
    with pytest.raises(ValueError, match="eigenvectors"):
        VibData(atoms, modes_invalid)
