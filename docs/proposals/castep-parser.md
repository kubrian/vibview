# Proposal: CASTEP Parser

> Parse CASTEP .phonon files for solid-state phonon visualization.

---

## Problem

CASTEP is a widely used plane-wave DFT code with built-in phonon capabilities (DFPT via the `phonon` task). Its `.phonon` output file contains lattice, atoms, frequencies, and eigenvectors for each q-point along a specified path. vibview currently supports Phonopy YAML and ORCA, but not CASTEP directly.

## Diagnosis

- CASTEP's `.phonon` file is a structured plain-text format with clear delimiters.
- It contains all the data needed for vibview: lattice vectors, atomic positions/fractional coordinates, frequencies, eigenvectors (real and imaginary parts per q-point).
- No parser currently handles this format.
- CASTEP users must convert to Phonopy format first — an extra, error-prone step.

## Proposed solution

Add `src/vibview/parsers/castep.py` for the `.phonon` format.

### File format

The `.phonon` file is line-oriented with block headers:

```
# CASM        =   xxxx
# NB.......
# q-pos =    0.0000000    0.0000000    0.0000000
#     Frequency (cm**-1)         Irrep
        0.00000                    1
        0.00000                    1
      123.45678                    2
      789.01234                    3
...
#     Mode     Atom     X                   Y                   Z
         1        1    0.7071068  0.0000   0.7071068  0.0000   0.0000000  0.0000
         1        2    0.7071068  0.0000   0.7071068  0.0000   0.0000000  0.0000
...
BEGIN header
...
END header
```

Key sections:

- `# q-pos = ...` — q-point coordinates (fractional).
- `# Frequency (cm**-1)` — frequency table, one per mode, with optional irrep label.
- `# Mode Atom X Y Z` — eigenvector blocks (real and imaginary parts as pairs: `REAL IMAG`).
- `BEGIN header ... END header` — contains lattice vectors, atomic coordinates, and masses.
- Irrep labels in the frequency table (e.g. `Irrep` column header, values like `T2g`, `A1g`).

### Extraction logic

1. **Header block** (`BEGIN header ... END header`):
   - Parse `lattice_vector` lines → 3×3 lattice matrix.
   - Parse `frac_coord` or `cart_coord` lines → atomic positions.
   - Parse `species` lines → element symbols (atomic numbers → symbol mapping).
   - Parse `mass` lines → atomic masses (optional, for reference).

2. **Q-point loop**:
   - For each `# q-pos = ...` block:
     - Read frequency table (real values in cm⁻¹, fractional imag for negative frequencies).
     - Read eigenvector blocks — each has `n_atoms × n_modes` entries. Format: `mode atom real_x imag_x real_y imag_y real_z imag_z`.
     - Convert to complex eigenvectors of shape `(n_modes, n_atoms, 3)`.

3. **Negative frequencies**: CASTEP writes imaginary frequencies as `0.00000 10.00000i` or similar. Parse the real part before the imaginary marker. Store as negative frequency (consistent with the existing `frequency` field; `ModeSelectorPanel` already handles negative frequencies with imaginary coloring).

4. **Lazy loading**: The `.phonon` file is read sequentially. Build a loader that scans to a given q-point index by counting `# q-pos = ...` markers, then parses that block on demand. This mimics the Phonopy lazy loader pattern.

### Registration

```python
"castep": caste.parse
```

### Tests

- Create a minimal `.phonon` fixture with 2 atoms and 6 modes (diamond at Γ).
- Test atom/position parsing, lattice extraction.
- Test frequency and eigenvector parsing.
- Test multi-q-point data with path ordering.
- Test imaginary frequency parsing.
- Test lazy loading.

## Difficulties and considerations

### Format variability

CASTEP's `.phonon` format has minor variations across versions (CASTEP 20.x vs 22.x):

- The `BEGIN header` block may or may not contain `mass` lines (masses are optional in newer versions).
- Irrep labels in the frequency table are present only with `phonon_calc_irreps=True`.
- Eigenvector output is controlled by `phonon_write_eigenvectors=True` (must be on).

**Mitigation**: Clearly document required CASTEP settings. Make irrep label parsing optional (gracefully skip if absent). Fall back to standard atomic masses if `mass` lines are missing.

### Coordinate system

CASTEP uses fractional coordinates internally. Convert to Cartesian using the lattice matrix (matching the Phonopy parser pattern in `phonopy.py:84-85`).

### Eigenvector orientation

CASTEP eigenvectors represent atomic displacements (not mass-weighted). This matches vibview's convention — no mass de-weighting needed (unlike Phonopy/VASP). Confirm this in the CASTEP documentation and validate with a test case.

### Large files

Phonon dispersion calculations can produce large `.phonon` files (hundreds of KB to tens of MB for dense paths). The lazy-loading strategy mitigates memory use. The initial header read is fast.

### Edge case — single q-point

Some CASTEP runs produce a `.phonon` file with only the Γ-point (no path). The parser must handle this case identically to the molecular parser path (no lazy loader, single set of modes).

### Q-point path labels

CASTEP's `.phonon` file does not include high-symmetry point labels (Γ, X, etc.). These must be inferred from q-point coordinates or provided separately. For phase 1, omit labels — use q-point index only. This aligns with the band-structure viewer proposal's Phase 1 approach.

## Rationale

- CASTEP is widely used in the solid-state phonon community (UK/Europe, materials science).
- The `.phonon` format is self-contained (lattice + atoms + frequencies + eigenvectors in one file).
- Eigenvectors are already Cartesian — no mass de-weighting needed, reducing complexity.
- The Phonopy parser serves as a template (similar lazy-loading pattern, similar q-point iteration).
