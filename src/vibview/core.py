"""Structure representation, frame generation, and bond detection."""

from collections.abc import Callable

import numpy as np

from vibview.config import Config
from vibview.models import Mode, VibData


class Structure:
    """Atoms and vibrational modes (molecular or periodic)."""

    def __init__(
        self,
        data: VibData,
        qpoint_loader: Callable[[int], list[Mode]] | None,
    ):
        self.data = data
        self.qpoint_index: int = 0
        self.qpoint_loader = qpoint_loader
        self.atoms = data.atoms
        self.data.modes.sort(key=lambda m: m.frequency)
        self.modes = data.modes
        self.xyz = np.array([a.xyz for a in self.atoms])

    @property
    def is_crystal(self) -> bool:
        """Whether this structure is periodic (has q-points and lattice)."""
        return self.data.qpoints is not None

    def get_mode(self, position: int) -> Mode:
        """Get a vibrational mode by its frequency-sorted position.

        Args:
            position: The 0-based position in the frequency-sorted list.

        Returns:
            The matching Mode.

        Raises:
            IndexError: If position is out of range.
        """
        return self.modes[position]

    def detect_bonds(
        self, tolerance: float, config: Config
    ) -> list[tuple[int, int, float]]:
        """Detect bonds between atoms based on covalent radii.

        Args:
            tolerance: Additional distance tolerance beyond summed radii (Å).
            config: Config with element data.

        Returns:
            List of (i, j, distance) tuples for each detected bond.

        Raises:
            KeyError: If an atom symbol is not in the element database.
        """
        bonds: list[tuple[int, int, float]] = []
        n = len(self.atoms)
        for i in range(n):
            for j in range(i + 1, n):
                r1 = config.elements[self.atoms[i].symbol].radius
                r2 = config.elements[self.atoms[j].symbol].radius
                cutoff = r1 + r2 + tolerance
                d = np.linalg.norm(self.xyz[i] - self.xyz[j])
                if d < cutoff:
                    bonds.append((i, j, d))
        return bonds

    def switch_qpoint(self, qpoint_index: int) -> None:
        if self.qpoint_loader is None:
            raise ValueError("No q-point data available")
        if not 0 <= qpoint_index < len(self.data.qpoints):
            raise ValueError(
                f"qpoint_index {qpoint_index} out of range (0–{len(self.data.qpoints) - 1})"
            )
        self.qpoint_index = qpoint_index
        self.data.modes = self.qpoint_loader(qpoint_index)
        self.data.modes.sort(key=lambda m: m.frequency)
        self.modes = self.data.modes


def displacement_scale(eigenvectors: np.ndarray, amplitude: float) -> float:
    """Compute scalar so that the max per-atom 3D displacement = amplitude.

    For each atom the 3D displacement at peak equals
    ``scale * eigenvector[i]``, whose norm is ``amplitude`` for the atom
    with the largest eigenvector norm.

    Args:
        eigenvectors: Array of shape ``(n_atoms, 3)``.
        amplitude: Desired maximum displacement in angstroms.

    Returns:
        The scale factor to apply to the eigenvectors.
    """
    max_norm = np.linalg.norm(eigenvectors, axis=1).max()
    if max_norm > 1e-12:
        return amplitude / max_norm
    return 0.0


def _cell_offsets(
    supercell: tuple[int, int, int],
) -> np.ndarray:
    """Generate fractional offsets for each cell in a supercell.

    For ``(1, 1, 1)`` returns a single row ``[[0, 0, 0]]`` (the identity
    offset for the origin cell).

    Args:
        supercell: (Nx, Ny, Nz) supercell dimensions.

    Returns:
        (n_cells, 3) array of fractional offsets for each cell.
    """
    nx, ny, nz = supercell
    i, j, k = np.mgrid[:nx, :ny, :nz]
    return np.column_stack([i.ravel(), j.ravel(), k.ravel()]).astype(np.float64)


def generate_frames(
    structure: Structure,
    mode_index: int,
    frames: int,
    amplitude: float,
    cycles: int,
    supercell: tuple[int, int, int] | None,
) -> np.ndarray:
    """Generate animation frames for a given vibrational mode.

    Supports both single-cell (molecular) and supercell (periodic) modes.

    For single-cell use (``supercell`` is ``None`` or ``(1,1,1)``):
    the frame shape is ``(total_frames, n_atoms, 3)``.

    For supercell use (any dimension of ``supercell`` > 1):
    the frame shape is ``(total_frames, n_cells * n_atoms, 3)``.
    Each cell copy includes the inter-cell Bloch phase
    ``exp(i · 2π · q · R_c)``.

    Args:
        structure: The structure to animate.
        mode_index: Index of the vibrational mode (0-based).
        frames: Number of frames *per cycle* to generate.
        amplitude: Maximum atomic displacement amplitude in angstroms.
        cycles: Number of oscillation periods to cover (default 1).
        supercell: ``(Nx, Ny, Nz)`` supercell dimensions for periodic
            structures, or ``None`` for molecules (no lattice vectors
            needed; default ``None``).

    Returns:
        Array of shape ``(total_frames, N, 3)`` with displaced coordinates,
        where ``N`` is ``n_atoms`` for single-cell or ``n_cells * n_atoms``
        for supercell.

    Raises:
        ValueError: If the supercell path is requested but the structure
            has no lattice vectors.
    """
    mode = structure.get_mode(mode_index)
    eigenvectors = np.asarray(mode.eigenvectors, dtype=np.complex64)
    scale = displacement_scale(eigenvectors, amplitude)

    total = frames * cycles
    ts = np.arange(total) / frames

    is_supercell = supercell is not None and any(d > 1 for d in supercell)

    if is_supercell:
        lattice = structure.data.lattice
        if lattice is None:
            raise ValueError(
                "Supercell expansion requires lattice vectors; "
                "use supercell=None for molecules (non-periodic structures)"
            )
        lattice = np.array(lattice, dtype=np.float64)

        cell_offsets_frac = _cell_offsets(supercell)
        cell_offsets_cart = cell_offsets_frac @ lattice

        xyz = np.asarray(structure.xyz, dtype=np.float64)
        xyz_expanded = xyz[np.newaxis, :, :] + cell_offsets_cart[:, np.newaxis, :]
        xyz_expanded = xyz_expanded.reshape(-1, 3)

        q_point = structure.data.qpoints[structure.qpoint_index]
        q_frac = np.array(q_point, dtype=np.float64)
        theta = 2 * np.pi * (cell_offsets_frac @ q_frac)

        disp = scale * np.real(
            eigenvectors[np.newaxis, np.newaxis, :, :]
            * np.exp(
                1j
                * (
                    theta[np.newaxis, :, np.newaxis, np.newaxis]
                    - 2 * np.pi * ts[:, np.newaxis, np.newaxis, np.newaxis]
                )
            )
        )
        disp = disp.reshape(total, -1, 3)
        return xyz_expanded[np.newaxis, :, :] + disp

    # Single-cell (molecular) path
    displacements = scale * np.real(
        eigenvectors[np.newaxis, :, :]
        * np.exp(-1j * 2 * np.pi * ts[:, np.newaxis, np.newaxis])
    )
    return structure.xyz[np.newaxis, :, :] + displacements
