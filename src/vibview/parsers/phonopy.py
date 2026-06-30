"""Parser for self-contained phonopy YAML output (band.yaml / mesh.yaml).

Expects a YAML file with atomic data embedded under ``points``
(lattice, coordinates, masses).  No companion POSCAR is needed.
"""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import yaml

from vibview.models import Atom, Mode, ParseResult, VibData

_N_DIMS = 3


def _parse_eigenvector(ev_data: list, n_atoms: int, masses: list[float]) -> np.ndarray:
    if len(ev_data) != n_atoms:
        raise ValueError(
            f"Eigenvector has {len(ev_data)} atom entries, expected {n_atoms}"
        )

    flat = np.empty(n_atoms * _N_DIMS, dtype=np.complex64)
    for ai, atom_ev in enumerate(ev_data):
        if len(atom_ev) != _N_DIMS:
            raise ValueError(
                f"Atom {ai} in eigenvector has {len(atom_ev)} components, "
                f"expected {_N_DIMS}"
            )
        sqrt_mass = np.sqrt(masses[ai])
        for di, pair in enumerate(atom_ev):
            if not isinstance(pair, (list, tuple)) or len(pair) < 1:
                raise ValueError(
                    f"Atom {ai}, component {di}: expected [real, imag] pair, "
                    f"got {pair!r}"
                )
            re = float(pair[0]) if pair[0] is not None else 0.0
            im = float(pair[1]) if len(pair) > 1 and pair[1] is not None else 0.0
            flat[ai * _N_DIMS + di] = (re + 1j * im) / sqrt_mass

    norm = np.linalg.norm(flat)
    if norm > 1e-12:
        flat /= norm

    return flat.reshape(-1, _N_DIMS)


_YAML_LOADER = yaml.CSafeLoader if hasattr(yaml, "CSafeLoader") else yaml.SafeLoader


def _parse_header(
    lines: list[str], phonon_idx: int
) -> tuple[np.ndarray, list[Atom], list[float]]:
    header_text = "".join(lines[:phonon_idx])
    try:
        data = yaml.load(header_text, Loader=_YAML_LOADER)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse phonopy YAML header: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a YAML mapping in header, got {type(data).__name__}"
        )

    if not data.get("lattice"):
        raise ValueError("No 'lattice' section found in phonopy YAML")

    if not data.get("points"):
        raise ValueError("No 'points' section found in phonopy YAML")

    lattice = np.array(data["lattice"], dtype=float)
    points = data["points"]

    atoms: list[Atom] = []
    masses: list[float] = []
    for p in points:
        symbol = p.get("symbol")
        if not symbol:
            raise ValueError("Atom entry missing 'symbol'")
        coords = p.get("coordinates")
        if not coords or len(coords) != _N_DIMS:
            raise ValueError(f"Atom {symbol} missing or invalid 'coordinates'")
        frac = np.array(coords, dtype=float)
        cart = frac @ lattice
        atoms.append(Atom(symbol=symbol, xyz=cart.tolist()))
        m = p.get("mass")
        if m is None:
            raise ValueError(f"No mass for atom {symbol!r} in phonopy YAML")
        masses.append(float(m))

    return lattice, atoms, masses


def _parse_qpoint_entry(
    lines: list[str], start: int, end: int, n_atoms: int, masses: list[float]
) -> list[Mode]:
    text = "".join(lines[start:end])
    try:
        data = yaml.load(text, Loader=_YAML_LOADER)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse phonopy YAML q-point entry: {e}") from e
    entry = data[0]
    bands = entry["band"]
    q_modes: list[Mode] = []
    for bi, band in enumerate(bands):
        ev = _parse_eigenvector(band["eigenvector"], n_atoms, masses)
        q_modes.append(
            Mode(index=bi, eigenvectors=ev, frequency=float(band["frequency"]))
        )
    return q_modes


def _make_phonopy_loader(
    lines: list[str],
    qpoint_starts: list[int],
    n_atoms: int,
    masses: list[float],
) -> Callable[[int], list[Mode]]:
    """Create a loader that returns modes for a given q-point index."""

    def _load(qi: int) -> list[Mode]:
        end = qpoint_starts[qi + 1] if qi + 1 < len(qpoint_starts) else len(lines)
        return _parse_qpoint_entry(lines, qpoint_starts[qi], end, n_atoms, masses)

    return _load


def _find_qpoint_boundaries(
    lines: list[str], phonon_idx: int
) -> tuple[list[int], list[list[float]]]:
    starts: list[int] = []
    qpoints: list[list[float]] = []
    for i in range(phonon_idx + 1, len(lines)):
        line = lines[i]
        if line.startswith("- q-position:"):
            starts.append(i)
            start_bracket = line.index("[")
            end_bracket = line.index("]")
            parts = line[start_bracket + 1 : end_bracket].split(",")
            qpoints.append([float(p.strip()) for p in parts])
    return starts, qpoints


def parse(
    path: Path,
    qpoint_index: int,
) -> ParseResult:
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Phonopy YAML file not found: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        lines = f.readlines()

    phonon_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("phonon:"):
            phonon_idx = i
            break
    if phonon_idx is None:
        raise ValueError("No 'phonon' section found in phonopy YAML")

    lattice, atoms, masses = _parse_header(lines, phonon_idx)

    qpoint_starts, qpoints = _find_qpoint_boundaries(lines, phonon_idx)
    if not qpoints:
        raise ValueError("No q-points found in 'phonon' section")
    if not 0 <= qpoint_index < len(qpoints):
        raise ValueError(
            f"qpoint_index {qpoint_index} out of range (0–{len(qpoints) - 1})"
        )

    qp_loader = _make_phonopy_loader(lines, qpoint_starts, len(atoms), masses)
    initial_modes = _parse_qpoint_entry(
        lines,
        qpoint_starts[qpoint_index],
        qpoint_starts[qpoint_index + 1]
        if qpoint_index + 1 < len(qpoint_starts)
        else len(lines),
        len(atoms),
        masses,
    )

    return ParseResult(
        data=VibData(
            atoms=atoms,
            modes=initial_modes,
            qpoints=qpoints,
            lattice=lattice.tolist(),
            frequency_units="THz",
        ),
        source=str(yaml_path),
        qpoint_loader=qp_loader,
    )
