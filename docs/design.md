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
    index: int
    eigenvectors: np.ndarray  # complex64, shape (n_atoms, 3)
    frequency: float | None = None
    label: str | None = None
```

Eigenvectors are Cartesian displacement vectors in Å, L2-normalized over all 3N components (‖e‖ = 1). Frequency is optional. Negative frequencies (imaginary modes) are flagged (default red) in the mode list.

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
├── lattice                 [dataset: (3, 3) float64, optional]
├── qpoints                 [dataset: (Nq, 3) float64, optional]
└── atoms/
    ├── symbols             [dataset: (Nat,) UTF-8 string]
    └── positions           [dataset: (Nat, 3) float64, Å]
└── modes/
    ├── eigenvectors        [dataset: (Nmodes, Nat, 3) float64]
    │                       [crystal: (Nq, Nb, Nat, 3) float64]
    ├── frequencies         [dataset: (Nmodes,) float64]
    │   └── units           [attr: string, optional]
    └── labels              [dataset: (Nmodes,) UTF-8 string, optional]
```

Molecular data uses 3D eigenvectors; crystal data uses 4D. Crystal files use per-q-point chunking (`chunks=(1, n_bands, n_atoms, 3)`) to enable O(1) HDF5 seek for lazy loading.

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

Modes are selected by 0-based index. Frequency is displayed if present. Unit label uses `data.frequency_units` falling back to `config.display.frequency_units` (default `"?"`).

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
- **CLI flag removal:** Configuration is managed via YAML. Only `--mode` and `--qpoint` remain as quick data selection overrides. `vibview init-config` writes a fully-commented template.

---

## 6. Solid-State Support

Phonopy band.yaml/mesh.yaml parser supports multi-q-point data with lattice vectors. When `lattice` is present, the unit cell grid is drawn as a tube wireframe spanning all supercell cells — each edge is drawn exactly once using a +a/+b/+c direction rule.

- `--qpoint` selects the active q-point (0-based, default 0).
- Eigenvectors are stored per-q-point.

---

## 7. Tech Stack

| Component  | Library       | Rationale                            |
| ---------- | ------------- | ------------------------------------ |
| Rendering  | vispy + PyQt6 | OpenGL, standalone, X forwarding     |
| Data       | numpy         | Numerical operations                 |
| File I/O   | h5py          | HDF5: compression, random access     |
| Config I/O | pyyaml        | YAML parsing                         |
| GIF export | Pillow        | Lightweight; no external deps needed |
| MP4 export | imageio       | H.264 via ffmpeg binary on $PATH     |

`requires-python = ">=3.10"` for match-statement syntax and `X | Y` type unions.

---

## 8. Scope & Rationale

### In scope

- ORCA `.hess` parsing → animate/static/overlay visualization
- Phonopy band.yaml/mesh.yaml parsing → animate/static/overlay visualization (multi-q-point)
- Native HDF5 format for fast loading and compact storage
- Configurable appearance via YAML cascade
- PNG sequence, GIF, and MP4 export

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
| **WebM export**                           | MP4 covers current needs; no priority.                                                 |
| **Text-based native formats (JSON/YAML)** | HDF5 provides compression and random access that text formats cannot.                  |
| **`color_scheme` switching**              | CPK from built-in elements is sufficient; `rendering.atom_color` allows overrides.     |
| **IR/Raman intensities**                  | Viewer only — no analysis.                                                             |
| **`mass_weighted` override**              | Each parser handles its own normalisation; Core assumes Cartesian-normalised.          |
