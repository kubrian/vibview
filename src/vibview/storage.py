"""File-level I/O for the native vibview HDF5 format.

In-place mutations to previously dumped files — updating labels, and
(potentially) other metadata.  This is **not** about parsing
(file → VibData) or serialization (VibData → file), which live in
``parsers/native.py``.
"""

from pathlib import Path

import h5py
import numpy as np

from vibview.models import Mode


def _decode_bytes(val: bytes | str) -> str:
    return val.decode("utf-8") if isinstance(val, bytes) else val


def _read_labels(f: h5py.File, n_qpoints: int, n_modes: int) -> np.ndarray:
    if "/modes/labels" in f:
        raw = f["/modes/labels"][:]
        dt = h5py.string_dtype()
        if raw.dtype.kind in ("S", "O"):
            return np.array([_decode_bytes(v) for v in raw.flat], dtype=dt).reshape(
                raw.shape
            )
        return raw
    return np.full((n_qpoints, n_modes), "", dtype=h5py.string_dtype())


def _write_labels(f: h5py.File, data: np.ndarray) -> None:
    if "/modes/labels" in f:
        f["/modes/labels"][:] = data
    else:
        f.create_dataset("/modes/labels", data=data)


def update_labels(
    path: Path,
    modes: list[Mode],
    qpoint_index: int | None = None,
) -> None:
    """Update the /modes/labels dataset in-place in a native HDF5 file.

    For crystal files, only the row corresponding to *qpoint_index* is
    updated; all other q-points are preserved.

    If all labels are empty strings, the dataset is deleted entirely.

    Args:
        path: Path to an existing native vibview HDF5 file.
        modes: Current list of Mode objects whose ``.label`` values
            will be written.
        qpoint_index: Q-point index for crystal files; ``None`` for
            molecular (non-periodic) files.

    Raises:
        OSError: File cannot be opened for writing.
        KeyError: File is missing required HDF5 paths.
    """
    labels = np.array(
        [m.label if m.label is not None else "" for m in modes],
        dtype=h5py.string_dtype(),
    )

    with h5py.File(path, "r+") as f:
        if qpoint_index is not None:
            n_qpoints = f["/qpoints"].shape[0]
            current = _read_labels(f, n_qpoints, len(modes))
            current[qpoint_index] = labels
            if np.all(current == ""):
                if "/modes/labels" in f:
                    del f["/modes/labels"]
            else:
                _write_labels(f, current)
        else:
            has_labels = not np.all(labels == "")
            if has_labels:
                _write_labels(f, labels)
            elif "/modes/labels" in f:
                del f["/modes/labels"]
