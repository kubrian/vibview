# vibview — Design Document

> Standalone CLI tool for visualizing vibrational modes from computational chemistry.
> Post-processing viewer only — no analysis, no spectra.

---

## 1. Architecture & Data Model

### VibData (`models.py`)

Canonical interchange format produced by all parsers and consumed by the rendering pipeline.

| Field             | Type                | Optional | Notes                        |
| ----------------- | ------------------- | -------- | ---------------------------- |
| `atoms`           | `list[Atom]`        | No       |                              |
| `modes`           | `list[Mode]`        | No       | Active q-point modes (eager) |
| `qpoints`         | `list[list[float]]` | Yes      | Crystal data only            |
| `lattice`         | `list[list[float]]` | Yes      | 3×3 matrix in Å              |
| `frequency_units` | `str \| None`       | Yes      | From parser, e.g. `"cm⁻¹"`   |

### Atom

```python
@dataclass
class Atom:
    symbol: str
    xyz: list[float]
```

Cartesian coordinates in Å.

### Mode

```python
@dataclass
class Mode:
    eigenvectors: np.ndarray  # complex64 (internal), shape (n_atoms, 3)
    frequency: float | None = None
    label: str | None = None
```

Eigenvectors are Cartesian displacement vectors in Å, L2-normalized over all 3N components (‖e‖ = 1). Normalisation uses float64 arithmetic to guarantee a fixed point across re-parsing. Frequency is optional. Negative frequencies (imaginary modes) are flagged (default red) in the mode list.

Modes are frequency-sorted ascending at load time (both molecular and per-q-point for crystals). Modes with `frequency=None` sort after all numeric frequencies. The `#` column in the mode selector displays the 1-indexed frequency-sorted position.

---

## 2. Parsing

### Parser interface

Each parser module exposes `parse(path: Path, ...) -> ParseResult`. Post-parse validation checks atom count, eigenvector shape, and frequency type.

### Supported formats

| Parser    | Input                     | Notes                                     |
| --------- | ------------------------- | ----------------------------------------- |
| `native`  | `.h5`                     | Internal HDF5 format                      |
| `orca`    | `*.hess`                  | Frequencies + mass-weighted normal modes  |
| `phonopy` | `band.yaml` / `mesh.yaml` | Self-contained (lattice + atoms embedded) |

### Native HDF5 schema

```
/                           Root group
├── atoms/
│   ├── symbols             [dataset: (Nat,) UTF-8 string]
│   └── positions           [dataset: (Nat, 3) float64, Å]
├── lattice                 [dataset: (3, 3) float64, optional]
├── qpoints                 [dataset: (Nq, 3) float64, optional]
└── modes/
    ├── eigenvectors        [dataset: (Nmodes, Nat, 3) float16] — molecular
    │                       [dataset: (Nq, Nb, Nat, 3, 2) float16] — crystal
    │                       crystal last dim = (real, imag); upcast to complex64 on read
    ├── frequencies         [dataset: (Nmodes,) float64]
    │   └── units           [attr: string, optional]
    └── labels              [dataset: (Nmodes,) UTF-8 string, optional]
```

Molecular: 3D float16 eigenvectors (real only). Crystal: 5D float16 stacked as `(real, imag)` pairs, halving file size with no visible quality loss. Both use per-q-point chunking to enable O(1) HDF5 seek for lazy loading.

### Eigenvector precision rationale

Crystal eigenvectors are stored as **float16** (half-precision IEEE 754) real/imaginary pairs rather than complex64 (float32). This was chosen after benchmarking on a 56 MB phonopy file (204 q-points × 72 bands × 24 atoms):

| Storage    | File size | Angular error (max) | Notes                           |
| ---------- | :-------: | :-----------------: | ------------------------------- |
| complex64  |  7.58 MB  |          0          | Baseline                        |
| float16 ×2 |  3.76 MB  |       0.0004°       | 50% reduction, no visual impact |

float16 precision (~0.001 for unit-vector components) is 100× beyond what is needed for pixel-level rendering on 2000 px displays. `Mode.__post_init__` normalizes using float64 arithmetic before downcasting to complex64 for internal use, so the on-disk format has no effect on computation precision.

### Lazy loading

Crystal files load only the first q-point eagerly. Subsequent q-points are loaded on demand via a cached loader built by `make_qpoint_loader()`. Phonopy's lazy loader slices the already-loaded YAML lines list.

---

## 3. Viewing

### Smart Loading

`vibview view` supports direct loading of any supported format for quick exploration. When loading a non-native format, the tool performs an in-memory conversion but emits a warning recommending a permanent conversion to the native format for better performance.

### Visualization modes

Three modes are selectable via the UI buttons (`Animate`, `Static`, `Overlay`):

| UI label    | Visual                                                                    |
| ----------- | ------------------------------------------------------------------------- |
| **Animate** | Atoms oscillate sinusoidally: `x(t) = x₀ + A·e·sin(2πt/T)`                |
| **Static**  | Orange displacement arrows (shaft + cone), length ∝ amplitude             |
| **Overlay** | Equilibrium (blue wireframe) + displaced (semi-transparent red wireframe) |

### Mode selection & frequency display

Modes are selected by frequency-sorted position (0-based internally, 1-indexed in the table UI). Frequency is displayed if present with default sort ascending on this column. Unit label uses `data.frequency_units` falling back to `config.display.frequency_units` (default `"?"`). Labels are editable inline for native HDF5 files only; editing sets a dirty flag and enables a Save Labels button. Switching q-points with dirty labels shows a confirmation dialog.

### Animation engine

The engine uses pre-computed merged meshes for every animation frame. All N × 2 meshes are built once and stay resident on the GPU. During playback, `update()` toggles `visible` on the previous and current frame's meshes.

- **Draw calls:** 2 per frame (atoms + bonds).
- **Animation overhead:** ~0 ms (zero per-frame vertex upload).
- **Frame rate:** 60 fps interactive.

This approach was chosen over alternatives:

- _Individual Sphere/Tube:_ Too many draw calls, causing GPU bottlenecks.
- _Merged mesh with per-frame `set_vertices()`:_ Shifted the bottleneck to PCIe bandwidth due to constant vertex uploads.
- _GPU-side VBO cycling:_ Not natively exposed by `vispy.scene.visuals.Mesh`; requires complex custom `Visual` subclasses or shader workarounds which are not necessary given the current performance.

### Camera & navigation

Rotate via mouse drag, zoom via scroll, pan via middle-mouse drag or Shift+left drag. Center of mass is used as origin. Reset view via `R` key. Fullscreen via `F11` key.

---

## 4. Export

### Strict Enforcement

`vibview export` strictly requires the native HDF5 format to ensure robust, high-performance animation rendering. Non-native files must be converted using `vibview convert` prior to export.

### `vibview convert`

`vibview convert` re-exports parsed data as native HDF5. For crystal data, all q-points are materialized into the output file, facilitating faster loading and reduced disk size via gzip compression.

### Animation export

| Format | Mechanism              | Notes                                   |
| ------ | ---------------------- | --------------------------------------- |
| PNG    | Frame-by-frame capture | No external deps                        |
| GIF    | Pillow                 | Universal, 256-colour palette           |
| MP4    | imageio + ffmpeg       | H.264, 24-bit colour, inter-frame comp. |

`ffmpeg` must be on `$PATH` for MP4 export; the tool raises a clear error with install instructions if missing.

---

## 5. Configuration

### Cascade

CLI overrides > `--config` session YAML > `~/.config/vibview/config.yaml` > package defaults (`vibview/data/defaults.yaml`).

### Design decisions

- **Configuration Objects:** `VibviewWindow` and `ModeSelectorPanel` accept `Config` objects.
- **Flat YAML sections:** Every section (`rendering:`, `animation:`, etc.) maps 1:1 to a dataclass.
- **Quality control:** `rendering.quality` (`low|medium|high`) controls sphere tessellation. `shading` (`null`/`"flat"`/`"smooth"`) controls the lighting model.
- **Lighting, camera, and axis:** These are configurable via dedicated YAML sections.
- **Per-mode amplitudes:** `static.amplitude` and `overlay.amplitude` define displacement amplitudes.
- **Bond detection:** Uses covalent radii + `bond_tolerance`. This method is preferred over a `fixed_cutoff` as it is more physically principled and a single method is sufficient.
- **Per-element overrides:** Element data lives in the `elements:` section of `defaults.yaml` (single source of truth). Any config layer can override individual radii, colours, and masses.
- **CLI flag removal:** Configuration is managed via YAML. Only `--mode`, `--qpoint`, and `--example` remain as quick data selection overrides. `vibview init-config` writes a fully-commented template.

---

## 6. Solid-State Support

Phonopy band.yaml/mesh.yaml parser supports multi-q-point data with lattice vectors. When `lattice` is present, the unit cell grid is drawn as a tube wireframe spanning all supercell cells — each edge is drawn exactly once using a +a/+b/+c direction rule.

- `--qpoint` selects the active q-point (0-based, default 0).
- Eigenvectors are stored per-q-point.

---

## 7. Tech Stack

| Component  | Library             | Rationale                            |
| ---------- | ------------------- | ------------------------------------ |
| Rendering  | vispy + PyQt6       | OpenGL, standalone, X forwarding     |
| Platforms  | Linux/macOS/Windows | Cross-platform via pixi/conda-forge  |
| Data       | numpy               | Numerical operations                 |
| File I/O   | h5py                | HDF5: compression, random access     |
| Config I/O | pyyaml              | YAML parsing                         |
| GIF export | Pillow              | Lightweight; no external deps needed |
| MP4 export | imageio             | H.264 via ffmpeg binary on $PATH     |

`requires-python = ">=3.10"` for match-statement syntax and `X | Y` type unions.

---

## 8. Scope & Rationale

### Deferred (may revisit)

- Conda packaging
- Cell-centered camera

### Alternatives considered and rejected

| Decision                                  | Rationale                                                                              |
| ----------------------------------------- | -------------------------------------------------------------------------------------- |
| **Jupyter/nglview backend**               | CLI-first design. `vispy`+`PyQt6` works over SSH/X11. Two backends double maintenance. |
| **`cclib` dependency**                    | Large and complex. Custom parsers provide better control and a smaller footprint.      |
| **`phonopy` Python API**                  | Heavy dependency. Custom YAML parser is sufficient.                                    |
| **Additional parsers (VASP, Gaussian)**   | Not needed for current use cases. Adding only upon demand.                             |
| **Text-based native formats (JSON/YAML)** | HDF5 provides compression and random access that text formats cannot.                  |
| **IR/Raman intensities**                  | Viewer only — no analysis.                                                             |
