# Proposal: Band-Structure Viewer

> Add a 2D phonon dispersion panel (frequency vs. q-path) with click-to-animate interaction.

---

## Problem

vibview can visualize modes at any single q-point, but users cannot **see** how frequencies vary across the Brillouin zone. The original use case (`scratch/use_case.md`) asks to "understand degeneracies in phonons at specific crossings for K-path based phonon data." There is currently no way to:

- View a dispersion curve alongside the 3D view.
- Click on a band at a given q-point to animate that mode.
- Navigate along a K-path and see the mode evolve.

Competitors (phononwebsite, Euphonic, VASP AniMove) all offer some form of band-structure + mode preview. vibview is missing this entirely.

## Diagnosis

### Current state

- **Q-point model**: vibview loads one q-point at a time. `Structure.switch_qpoint(qi)` replaces `self.modes` with the new q-point's modes. Lazy loading is per-q-point.
- **No path concept**: q-points are a flat list (`data.qpoints: list[list[float]]`), not an ordered path with segment labels (Γ→X→W→Γ, etc.).
- **No 2D plotting**: vispy can do 2D via `vispy.scene.visuals.Line` and `Markers`, but vibview has no 2D view or panel infrastructure.
- **UI architecture**: `VibviewWindow` is a `QMainWindow` with a `QSplitter` (3D canvas + mode panel). There's no sidebar or secondary viewport.

### Why this is hard

1. **Data representation**: `VibData.qpoints` is a flat list without semantic path information (labels, segment ordering, distances). Phonopy band.yaml has `phonon:` entries in file order, but the path labels are metadata not currently stored.
2. **Band continuity**: Modes at consecutive q-points have the same index but may not correspond to the same physical band — band crossings make index-based matching incorrect. Proper band unfolding requires overlap integrals (`⟨e(q_i) | e(q_{i+1})⟩`).
3. **Lazy loading**: Crystal files lazy-load q-points. A band plot needs all q-points loaded (at least frequencies) upfront, which defeats the lazy-load optimization for the plot data.
4. **Interaction channel**: Clicking a point on the band plot must trigger a q-point + mode switch in the 3D viewer. This requires a cross-controller communication path that doesn't exist yet.

## Proposed solution

### Phase 1 — Minimal viable band plot (scatter, no routing, no continuity)

A lightweight scatter-only overlay that makes no attempt to track bands across q-points. Suitable for mesh.yaml (irregular q-grid) and simple band.yaml files.

**What it does**:

- Renders frequency vs. q-point index as a scatter plot (one color per band).
- Clicking a point loads that q-point + mode index in the main 3D view.
- Works as a toggleable dock widget alongside the mode panel.

**What it does NOT do**:

- No line plot — points are independent, so no band continuity / matching is needed.
- No K-path labels (Γ, X, etc.) — uses q-point index as x-axis.
- No band unfolding at crossings.
- No interpolation between q-points.

### Phase 2 — Full band structure (bands across ordered K-path)

For band.yaml files with known high-symmetry paths.

**Additions**:

- Parse K-path labels from phonopy YAML (present as comments or `label` fields).
- Compute cumulative q-point distances for a physically meaningful x-axis.
- Implement band continuity via eigenvector overlap: `O_mn(q) = ⟨e_m(q) | e_n(q+δq)⟩`. At each q-step, reorder bands by maximum overlap with the previous q-point.
- Label high-symmetry points on the x-axis.

### Data model changes

Add to `VibData`:

```python
@dataclass
class QPoint:
    q: list[float]
    label: str | None = None  # e.g. "Γ", "X", "L"

# In VibData:
qpoints: list[QPoint] | None = None  # replaces list[list[float]]
```

This is a breaking data model change — all parsers and serializers must be updated atomically.

### Architecture changes

#### New module: `src/vibview/renderers/band_structure_panel.py`

A new sub-controller that manages:

- A `vispy.scene.SceneCanvas` for the 2D plot (embedded in a `QWidget`).
- A `matplotlib`-style plot area with axes, labels, grid.
- Mouse-click picking via `canvas.events.mouse_press`.

```python
class BandStructurePanel:
    def __init__(self, structure, config):
        self.structure = structure
        self.canvas = SceneCanvas(..., bgcolor="white")
        self._build_plot()

    def _load_frequencies(self):
        # Eagerly load frequencies for all q-points
        # (required for the plot; lazy loading is bypassed)

    def _build_plot(self):
        # Draw lines/points using vispy Line + Markers

    def on_click(self, event):
        # Map click → (qpoint_index, mode_index)
        # Emit callback
```

#### Changes to `VibviewWindow`

- Add a `QSplitter` (or dock widget) for the band panel, alongside the 3D canvas.
- Connect `BandStructurePanel.on_click` → `VispyViewer.switch_qpoint()` + `switch_mode()`.

#### Changes to `Structure` / `VibData`

- Add `qpoint_labels: list[str | None]` property (derived from `QPoint.label`).
- Add method `load_all_qpoint_frequencies() -> np.ndarray` for eager frequency loading.

#### Changes to phonopy parser

- Optionally read K-path labels from band.yaml (present as `label:` fields or line comments).
- Return `QPoint` objects instead of raw `list[float]`.

#### Changes to native HDF5 parser

- Read/write `qpoints` with optional label metadata (new dataset `/qpoints/labels` or as attribute).

#### Changes to native HDF5 writer (`dump`)

- Write `qpoint_labels` dataset alongside `qpoints`.

### UI/UX

```
┌──────────────────────────────────────┐
│ ┌──────────────────┐ ┌────────────┐ │
│ │                  │ │ Mode Panel │ │
│ │   3D View        │ │ (existing) │ │
│ │                  │ │            │ │
│ │                  │ ├────────────┤ │
│ │                  │ │ Band Plot  │ │
│ │                  │ │ (new)      │ │
│ └──────────────────┘ └────────────┘ │
└──────────────────────────────────────┘
```

The band plot is a dockable panel. Users can:

- Toggle it on/off via a menu item or button.
- Click any point → 3D view switches to that q-point + mode.
- Hover for tooltip: `q=(0,0,0), mode=3, ω=1245 cm⁻¹`.
- Zoom/pan the plot independently from the 3D view.

## Difficulties and considerations

### Core design impact — data model change

Replacing `qpoints: list[list[float]]` with `qpoints: list[QPoint]` is a **breaking change** to the `VibData` dataclass. All parsers, serializers, and consumers must be updated. Accepted — no compat shim or migration layer.

### Core design impact — eager frequency loading

The band plot needs frequencies for all q-points upfront. This:

- Defeats lazy loading for the plot module.
- Increases initial memory use (which may be significant for dense meshes).
- Is acceptable because frequencies are small (Nq × Nb floats) compared to eigenvectors (Nq × Nb × Nat × 3 complex64).

**Mitigation**: Load only frequencies, not eigenvectors, for the plot. The HDF5 native parser stores frequencies as a separate (Nq, Nb) chunked dataset — this can be read without loading eigenvectors. The phonopy lazy loader also has frequencies in the YAML text, so they can be extracted without full eigenvector processing.

### Band continuity — eigenvector overlap (Phase 2 only)

This is the hardest technical challenge, and it only applies to line plots. At a band crossing, mode indices swap. A naive line plot (connecting same-index points across q) shows discontinuities. A scatter plot avoids this entirely because each point is independent — no matching needed.

**Solution for Phase 2 line plots**: Implement overlap-based sorting:

```python
def _reorder_by_overlap(modes_q: list[Mode], modes_q_next: list[Mode]) -> list[int]:
    """Return permutation that maximizes overlap between q and q+δq."""
    n = len(modes_q)
    overlap = np.zeros((n, n), dtype=np.complex64)
    for i in range(n):
        for j in range(n):
            overlap[i, j] = np.vdot(modes_q[i].eigenvectors.ravel(),
                                    modes_q_next[j].eigenvectors.ravel())
    # Greedy matching: pair each mode at q with the best match at q+δq
    perm = []
    available = set(range(n))
    for i in range(n):
        best_j = max(available, key=lambda j: np.abs(overlap[i, j]))
        perm.append(best_j)
        available.remove(best_j)
    return perm
```

The code example shows greedy matching (O(n²)), which is sufficient for typical band counts (≤100). If Phase 2 ever needs scipy's Hungarian algorithm for higher accuracy, that can be added locally — but start with greedy.

### Lazy-loading bypass for the plot

The plot needs frequencies for all q-points. For native HDF5, this means reading `/modes/frequencies` with shape (Nq, Nb) — a single contiguous read, fast. For phonopy YAML, frequencies are in the text and already loaded.

**No change needed** to the lazy loading architecture — the plot module bypasses it with its own eager read.

### vispy 2D plotting limitations

vispy's 2D support is adequate but not as polished as matplotlib. Key considerations:

- `vispy.scene.visuals.Line` + `Markers` work well for scatter/line plots.
- Text labels (high-symmetry point names) need `vispy.scene.visuals.Text`.
- Axis ticks/labels require manual placement or a custom `AxisVisual`.
- Tooltips on hover require `vispy.app.Canvas.events.mouse_move` + picking.

**Alternative**: Use `matplotlib` embedded via `FigureCanvasQTAgg`. This gives publication-quality plots for free. However, it adds a matplotlib dependency (currently not listed) and two rendering backends. Since vibview already uses Qt6, `FigureCanvasQTAgg` from `matplotlib.backends.backend_qtagg` works natively.

**Recommendation**: Use vispy for the plot to avoid adding matplotlib as a dependency. If vispy proves insufficient, downgrading to a matplotlib-based panel is a local change (the `BandStructurePanel` abstraction isolates the rendering backend).

### Scope creep risk

The band-structure viewer is the single largest feature addition in scope. It touches:

- `models.py` — data model change
- `core.py` — qpoint reordering
- `parsers/phonopy.py` — path labels
- `parsers/native.py` — label serialization
- `renderers/` — new module + window integration
- `tests/` — new test file
- `pyproject.toml` — potential scipy dependency

**Mitigation**: Phase 1 intentionally avoids band continuity and path labels. Phase 1 can be delivered in ~2 weeks; Phase 2 adds ~2 more weeks. Ship Phase 1 first.

## Rationale

- Closes the biggest functional gap vs. phononwebsite and Euphonic.
- Directly serves the stated use case (degeneracy understanding at K-path crossings).
- Phase 1 deliverable is achievable and provides value even without full band continuity.
- The `QPoint` data model change is overdue — float lists without labels lose information that parsers already have.
