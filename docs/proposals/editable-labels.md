# Proposal: Editable Mode Labels

> Make the Label column in the mode table editable and persist changes back to the source HDF5 file.

---

## Problem

The Label column in the mode table displays each `Mode.label` string (or an italicized em-dash for `None`), but the cells are read-only. A user who wants to annotate modes (e.g. "O-H symmetric stretch", "umbrella mode") has no way to type or save that annotation.

## Diagnosis

- `Mode.label: str | None` already exists in the data model (`src/vibview/models.py:30`).
- Native HDF5 parser reads/writes labels in full (`src/vibview/parsers/native.py`).
- The table in `ModeSelectorPanel` (`src/vibview/renderers/qt_window.py:131`) sets `NoEditTriggers` — the entire table is read-only.
- No mechanism exists to write label changes back to the source file.
- The source file path is available in `ParseResult.source` but never forwarded to the UI.

## Proposed solution

### Design: In-memory edit + explicit "Save Labels" button

Edits update `Mode.label` in memory immediately (visible in the UI), but only persist to disk when the user clicks a dedicated **Save Labels** button. This avoids HDF5 write risk on every keystroke and follows a familiar save-document paradigm.

### Changes

#### 1. Make Label column editable (`qt_window.py`)

- Change edit triggers from `NoEditTriggers` to `DoubleClicked`.
- In `_rebuild_table`, set `ItemIsEditable` on column-2 items only. Keep columns 0 (#) and 1 (Freq) read-only.
- Connect `table.cellChanged` → `_on_label_edited(row, col)`:
  - Ignore `col != 2`.
  - Resolve the mode index from column 0's `UserRole` data.
  - Update `self._modes[idx].label` with the new text (empty string → `None`).
  - Set `self._labels_dirty = True`.

#### 2. Add Save Labels button (`qt_window.py`)

- `QPushButton("Save Labels")` in the Data section, initially hidden.
- Shown when `_labels_dirty` is `True`.
- Connected to `_on_save_labels()`:
  - **Native files (`.h5`)**: call `native.update_labels(path, self._modes, ...)` for in-place update.
  - **Non-native files**: open a "Save As" dialog → user picks a new `.h5` path → call `dump_native` to write a full native file (includes labels).
  - Clear dirty flag, hide button, update window title.

#### 3. Dirty indicator (`VibviewWindow.setWindowTitle`)

- Append `*` to the title when `_labels_dirty` is `True` (e.g. `"VibView - h2o.h5*"`).
- Clear `*` on successful save.
- Reset dirty flag when switching q-point (labels reloaded from disk).

#### 4. Thread source path (`main.py` → `vispy_renderer.py` → `qt_window.py`)

- `VispyViewer.__init__` gains optional `source_path: str | None` and `source_format: str` params.
- Passed through to `VibviewWindow` → `ModeSelectorPanel`.
- `main.py` passes `result.source` and the parser format from CLI args.

#### 5. In-place label update (`native.py`)

New function `update_labels(path, modes, qpoint_index=None, qpoints=None)`:

```
def update_labels(path, modes, qpoint_index=None, qpoints=None):
    """
    Open an existing native HDF5 file in r+ mode and replace
    the /modes/labels dataset with the current in-memory labels.
    For molecular files: write a 1D string array.
    For crystal files: load all q-points' current labels,
    update the current q-point's row, write the 2D array back.
    """
```

Crystal case requires loading all q-point labels to preserve other rows. Accept the overhead — label data is small (a few KB even for hundreds of modes).

### Non-native format handling

ORCA and Phonopy files cannot be written back to. The Save Labels button prompts "Save As" → user creates a new `.h5` → subsequent saves go in-place to that `.h5`.

## Rationale

- **Save button over instant override**: Safer (batch write, no partial HDF5 corruption), deliberate UX, familiar pattern. Instant override would require per-edit HDF5 writes — fragile and potentially annoying.
- **In-place HDF5 update**: Avoids rewriting the entire file (all eigenvectors, frequencies, etc.) when only labels changed.
- **Read-only index/freq columns**: No use case for editing them — index is identity, frequency comes from the calculation.
- **Architecture fits**: Labels already live on `Mode`, the HDF5 schema already has a `labels` dataset, and `ParseResult.source` already tracks the file path. The work is purely in the UI and plumbing layers.
