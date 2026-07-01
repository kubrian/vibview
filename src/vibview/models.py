"""Core data types for atoms, modes, and parsed input."""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass
class Atom:
    """A single atom with element symbol and Cartesian coordinates."""

    symbol: str
    xyz: list[float]


@dataclass
class Mode:
    """A vibrational mode with eigenvectors and optional metadata.

    ``eigenvectors`` is a numpy array of shape ``(n_atoms, 3)`` with
    ``complex64`` dtype, normalized to unit vectors.

    Normalisation uses float64 arithmetic so that re-parsing a stored
    vector always produces the same canonical float32 representation.
    """

    eigenvectors: np.ndarray
    frequency: float | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        ev = np.asarray(self.eigenvectors, dtype=np.complex128)
        norm = np.linalg.norm(ev)
        if norm > 1e-12:
            ev /= norm
        self.eigenvectors = ev.astype(np.complex64)


@dataclass
class VibData:
    """Canonical representation of parsed vibrational data.

    This is the standard interchange format produced by all parsers
    and consumed by the core pipeline.
    """

    atoms: list[Atom]
    modes: list[Mode]
    qpoints: list[list[float]] | None = None
    lattice: list[list[float]] | None = None
    frequency_units: str | None = None

    def __post_init__(self):
        if not self.atoms:
            raise ValueError("Atoms list cannot be empty")
        for mode in self.modes:
            if len(mode.eigenvectors) != len(self.atoms):
                raise ValueError(
                    f"Mode has {len(mode.eigenvectors)} eigenvectors, expected {len(self.atoms)}"
                )


@dataclass
class ParseResult:
    """Result of parsing a file — data plus optional lazy-load capability.

    ``data`` is the fully constructed VibData.  ``qpoint_loader``, if set,
    provides on-demand loading of individual q-point mode sets for crystal
    data.  ``source`` is the originating file path, used internally by
    loaders that need to re-open the file.
    """

    data: VibData
    source: str | None = None
    qpoint_loader: Callable[[int], list[Mode]] | None = None
