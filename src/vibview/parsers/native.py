"""Parser and serializer for the native vibview HDF5 format.

Schema
------

**Molecular** (no lattice/qpoints)::

    /
    ├── atoms/
    │   ├── symbols         [dataset: (Nat,) UTF-8 string]
    │   └── positions       [dataset: (Nat, 3) float64]
    └── modes/
        ├── eigenvectors    [dataset: (Nb, Nat, 3) float64]
        ├── frequencies     [dataset: (Nb,) float64]  NaN = absent
        ├── labels          [dataset: (Nb,) UTF-8 string, optional]
        └── units           [attr on frequencies: string, optional]

**Crystal** (with lattice/qpoints)::

    /
    ├── lattice             [dataset: (3, 3) float64]
    ├── qpoints             [dataset: (Nq, 3) float64]
    ├── atoms/
    │   ├── symbols         [dataset: (Nat,) UTF-8 string]
    │   └── positions       [dataset: (Nat, 3) float64]
    └── modes/
        ├── eigenvectors    [dataset: (Nq, Nb, Nat, 3) complex64, chunked+gzip]
        ├── frequencies     [dataset: (Nq, Nb) float64, chunked+gzip]
        ├── labels          [dataset: (Nq, Nb) UTF-8 string, optional, chunked+gzip]
        └── units           [attr on frequencies: string, optional]
"""

from collections.abc import Callable
from pathlib import Path

import h5py
import numpy as np

from vibview.models import Atom, Mode, ParseResult, VibData


def _decode_bytes(val: bytes | str) -> str:
    return val.decode("utf-8") if isinstance(val, bytes) else val


def _read_modes_from_slice(
    ev_slice: np.ndarray,
    freq_slice: np.ndarray | None,
    labels_ds: h5py.Dataset | None,
    qi: int | None,
) -> list[Mode]:
    """Build a list of Mode from a slice of the eigenvectors array.

    Args:
        ev_slice: Eigenvectors slice, shape ``(Nb, Nat, 3)``.
        freq_slice: Frequencies slice, shape ``(Nb,)``, or None.
        labels_ds: Labels dataset (1D or 2D), indexed by *qi* when given.
        qi: Q-point index for labels indexing; None for 1D labels.
    """
    n_bands = ev_slice.shape[0]
    modes: list[Mode] = []
    for bi in range(n_bands):
        frequency = None
        if freq_slice is not None:
            v = float(freq_slice[bi])
            if not np.isnan(v):
                frequency = v

        label = None
        if labels_ds is not None:
            raw = labels_ds[bi] if qi is None else labels_ds[qi, bi]
            raw = _decode_bytes(raw) if isinstance(raw, bytes) else raw
            if raw:
                label = raw

        modes.append(
            Mode(
                index=bi,
                eigenvectors=ev_slice[bi].copy(),
                frequency=frequency,
                label=label,
            )
        )
    return modes


def _native_load_qpoint(source: Path, qi: int) -> list[Mode]:
    """Load a single q-point's modes from an HDF5 file."""
    with h5py.File(source, "r") as f:
        ev = f["/modes/eigenvectors"]
        freq = f.get("/modes/frequencies")
        labels_ds = f.get("/modes/labels")
        return _read_modes_from_slice(
            ev[qi], freq[qi] if freq is not None else None, labels_ds, qi
        )


def parse(path: Path) -> ParseResult:
    """Parse a native vibview HDF5 file into ParseResult.

    For crystal files (``/qpoints`` present), only the first q-point is
    loaded eagerly; the rest are loaded on demand from the source file.

    Args:
        path: Path to a .h5 file.

    Returns:
        A ParseResult containing the validated VibData.

    Raises:
        OSError: If the file cannot be opened or read.
        ValueError: If the file is malformed or required datasets are missing.
    """
    with h5py.File(path, "r") as f:
        if "/atoms/symbols" not in f or "/atoms/positions" not in f:
            raise ValueError(f"Missing /atoms datasets in {path}")

        symbols = f["/atoms/symbols"][:]
        positions = f["/atoms/positions"][:]

        symbols_list = [_decode_bytes(s) for s in symbols]
        atoms = [
            Atom(symbol=symbols_list[i], xyz=positions[i].tolist())
            for i in range(len(symbols_list))
        ]

        if "/modes/eigenvectors" not in f:
            raise ValueError(f"Missing /modes/eigenvectors dataset in {path}")

        ev_dataset = f["/modes/eigenvectors"]
        freq_ds = f.get("/modes/frequencies")
        labels_ds = f.get("/modes/labels")

        frequency_units = None
        if freq_ds is not None:
            raw = freq_ds.attrs.get("units")
            if raw is not None:
                frequency_units = _decode_bytes(raw) if isinstance(raw, bytes) else raw

        lattice = None
        if "/lattice" in f:
            lattice = f["/lattice"][:].tolist()

        qpoints = None
        is_crystal = "/qpoints" in f
        if is_crystal:
            qpoints = f["/qpoints"][:].tolist()

        if is_crystal:
            n_qpoints, n_bands, _, _ = ev_dataset.shape
            modes = _read_modes_from_slice(
                ev_dataset[0],
                freq_ds[0] if freq_ds is not None else None,
                labels_ds,
                qi=0,
            )
        else:
            n_bands, _, _ = ev_dataset.shape
            modes = _read_modes_from_slice(
                ev_dataset[:],
                freq_ds[:] if freq_ds is not None else None,
                labels_ds,
                qi=None,
            )

    qp_loader = (lambda qi: _native_load_qpoint(path, qi)) if is_crystal else None

    return ParseResult(
        data=VibData(
            atoms=atoms,
            modes=modes,
            qpoints=qpoints,
            lattice=lattice,
            frequency_units=frequency_units,
        ),
        source=str(path),
        qpoint_loader=qp_loader,
    )


def _write_hdf5_common(
    f: h5py.File,
    data: VibData,
    symbols: np.ndarray,
    positions: np.ndarray,
    freq_ds: h5py.Dataset | None,
    frequency_units: str | None,
):
    """Write common HDF5 structure: atoms, lattice, and frequency units."""
    grp_atoms = f.create_group("atoms")
    grp_atoms.create_dataset("symbols", data=symbols)
    grp_atoms.create_dataset("positions", data=positions)

    if data.lattice is not None:
        f.create_dataset("lattice", data=np.array(data.lattice, dtype=np.float64))

    if freq_ds is not None and frequency_units:
        freq_ds.attrs["units"] = frequency_units


def _dump_crystal(
    path: Path,
    data: VibData,
    symbols: np.ndarray,
    positions: np.ndarray,
    fu: str | None,
    qpoint_loader: Callable[[int], list[Mode]] | None,
    qpoint_index: int,
):
    """Serialize crystal VibData to native HDF5 format."""
    n_qpoints = len(data.qpoints)
    n_bands = len(data.modes)
    n_atoms = len(data.atoms)

    all_ev = np.zeros((n_qpoints, n_bands, n_atoms, 3), dtype=np.complex64)
    all_freq = np.full((n_qpoints, n_bands), np.nan, dtype=np.float64)
    has_labels = False
    all_labels = np.full((n_qpoints, n_bands), "", dtype=h5py.string_dtype())

    for qi in range(n_qpoints):
        if qpoint_loader is not None:
            modes_qi = qpoint_loader(qi)
        elif qi == qpoint_index:
            modes_qi = data.modes
        else:
            raise ValueError(f"Cannot access q-point {qi}: no qpoint_loader available")

        for bi, m in enumerate(modes_qi):
            all_ev[qi, bi] = m.eigenvectors
            if m.frequency is not None:
                all_freq[qi, bi] = m.frequency
            if m.label:
                has_labels = True
                all_labels[qi, bi] = m.label

    with h5py.File(path, "w") as f:
        grp_modes = f.create_group("modes")
        freq_ds = grp_modes.create_dataset(
            "frequencies",
            data=all_freq,
            chunks=(1, n_bands),
            compression="gzip",
            compression_opts=6,
        )
        _write_hdf5_common(f, data, symbols, positions, freq_ds, fu)
        grp_modes.create_dataset(
            "eigenvectors",
            data=all_ev,
            chunks=(1, n_bands, n_atoms, 3),
            compression="gzip",
            compression_opts=6,
        )
        if has_labels:
            grp_modes.create_dataset(
                "labels",
                data=all_labels,
                chunks=(1, n_bands),
                compression="gzip",
                compression_opts=6,
            )
        f.create_dataset("qpoints", data=np.array(data.qpoints, dtype=np.float64))


def _dump_molecular(
    path: Path,
    data: VibData,
    symbols: np.ndarray,
    positions: np.ndarray,
    fu: str | None,
):
    """Serialize molecular (non-crystal) VibData to native HDF5 format."""
    eigenvectors = np.array([m.eigenvectors.real for m in data.modes], dtype=np.float64)
    frequencies = np.array(
        [m.frequency if m.frequency is not None else np.nan for m in data.modes],
        dtype=np.float64,
    )

    has_labels = any(m.label is not None for m in data.modes)
    labels = None
    if has_labels:
        labels = np.array(
            [m.label if m.label is not None else "" for m in data.modes],
            dtype=h5py.string_dtype(),
        )

    with h5py.File(path, "w") as f:
        grp_modes = f.create_group("modes")
        freq_ds = grp_modes.create_dataset("frequencies", data=frequencies)
        _write_hdf5_common(f, data, symbols, positions, freq_ds, fu)
        grp_modes.create_dataset("eigenvectors", data=eigenvectors)
        if labels is not None:
            grp_modes.create_dataset("labels", data=labels)


def dump(
    data: VibData,
    path: Path,
    frequency_units: str | None = None,
    qpoint_loader: Callable[[int], list[Mode]] | None = None,
    qpoint_index: int = 0,
) -> None:
    """Serialize VibData to native vibview HDF5 format.

    For crystal data (``data.qpoints`` is set), **all** q-points are
    written using *qpoint_loader* (falling back to the current mode
    data for the active q-point index).

    Args:
        data: The internal format data to serialize.
        path: Output file path.
        frequency_units: Optional override for frequency units.
        qpoint_loader: Optional callable to load q-point modes on demand.
        qpoint_index: Active q-point index (used as fallback when no loader).

    Raises:
        ValueError: If q-point data is incomplete and cannot be accessed.
    """
    fu = data.frequency_units or frequency_units

    symbols = np.array([a.symbol for a in data.atoms], dtype=h5py.string_dtype())
    positions = np.array([a.xyz for a in data.atoms], dtype=np.float64)

    if data.qpoints is not None:
        _dump_crystal(path, data, symbols, positions, fu, qpoint_loader, qpoint_index)
    else:
        _dump_molecular(path, data, symbols, positions, fu)
