# Proposal: Gaussian Parser

> Parse Gaussian .log and .fchk files for molecular normal-mode visualization.

---

## Problem

Gaussian is the most widely used quantum chemistry package for molecular calculations. vibview currently supports ORCA (`.hess`) and Phonopy (YAML), but not Gaussian. Users who compute vibrational frequencies with Gaussian must convert to another format first — there is no direct path.

Gaussian is the dominant molecular quantum chemistry package, and its user base represents the largest potential audience for vibview.

## Diagnosis

- `parsers/__init__.py::PARSERS` has no "gaussian" entry.
- No code in the codebase handles Gaussian output formats.
- The `.log` format (human-readable text output) contains frequencies and normal modes and is the easiest to parse — no new dependencies or format-specific handling required.

## Proposed solution

Add a new parser module `src/vibview/parsers/gaussian.py` for the `.log` format.

### Format: `.log` parsing

**Relevant section** in a Gaussian .log file:

```
 Harmonic frequencies (cm**-1), IR intensities (KM/Mole), Raman scattering
 activities (A**4/AMU), depolarization ratios for plane and unpolarized
 incident light, reduced masses (AMU), force constants (mDyne/A):

                      1                      2                      3
                      1.2345                456.7890              789.1234
 ...
 Atom AN      X      Y      Z        X      Y      Z        X      Y      Z
   1   6     0.00   0.00   0.12     0.00   0.11  -0.01     0.00  -0.05   0.00
   2   1     0.00   0.00  -0.05     0.00  -0.04   0.00     0.00   0.02   0.00
 ...
```

**Extraction logic**:

1. Find the line starting with `" Harmonic frequencies (cm**-1)"` (note: this header varies slightly across versions — `Harmonic`, `Frequencies`, etc.).
2. Read frequency values in blocks of 3 (one per mode column).
3. Find the `"Atom AN"` header — this marks the eigenvector matrix.
4. Read atom rows; each row has 3 × n_modes displacement values (X, Y, Z per mode).
5. Atoms are read from the `"Standard orientation:"` section earlier in the file (Cartesian coordinates in Å).

The parser supports only **molecular** (non-periodic) Gaussian output. Crystal orbital calculations (periodic Gaussian) are out of scope.

### Format: `.fchk` parsing

**Formatted checkpoint format**: A flat key-value file with section headers:

```
This is a Gaussian-formatted checkpoint file
...
Number of atoms                        I                 N=           12
...
Cartesian Gradient
RSpin=  1 IPFlag=  0
  1.23456789E+00  2.34567890E+00 ...
...
Vib-E2
RSpin=  1 IPFlag=  3
  1.23456789E+00 -2.34567890E+00 ...
```

**Relevant keys**:

- `Number of atoms` → n_atoms
- `Current cartesian coordinates` → atomic positions
- `Atomic numbers` → element identification
- `Vib-E2` → normal mode eigenvectors (flattened, 3N × 3N matrix)
- `Freq` → vibrational frequencies
- `Force Constants` → (optional, for validation)

**Extraction logic**:

1. Read key-value pairs with line continuations (values fill 5 fields per line, 16 chars per field).
2. Convert atomic numbers to symbols via a lookup table.
3. Reshape `Vib-E2` into (n_modes, n_atoms, 3).

### Auto-detection

Files with `.log` extension (or files starting with `" Entering Gaussian System"`) are parsed as `.log`.

### Registration

Add to `PARSERS` dict:

```python
"gaussian": gaussian.parse
```

### New dependency

Formatted checkpoint parsing (`.fchk`) requires **no new dependencies** — it is pure string manipulation.

The `.log` parser also requires no new dependencies.

### Tests

- A minimal Gaussian .log fixture (H2O or CH4) with known frequencies and eigenvectors, stored in `tests/fixtures/`.
- Test that parsed atoms match expected positions.
- Test that parsed frequencies match expected values.
- Test that eigenvectors are L2-normalized (confirmed by `Mode.__post_init__`).
- Test error handling: malformed files, missing sections, version mismatches.

## Difficulties and considerations

### Gaussian version variation

Gaussian .log format has changed between versions (G03, G09, G16, G16-C.01+). The header for frequencies section varies:

- G09: `"Harmonic frequencies (cm**-1)"`
- G16: `"Frequencies --"` (in some outputs)
- The `"Atom AN"` header is stable but column widths can vary.

**Mitigation**: Use regex-based pattern matching for section detection instead of fixed string matching. Test against outputs from at least G09 and G16.

### Coordinate systems

Gaussian's `"Standard orientation:"` gives Cartesian coordinates in Å. The `"Input orientation:"` section gives coordinates in the input frame. Use "Standard orientation" exclusively — it is the most reliable across calculation types.

### Mass-weighting

Gaussian `.log` files print Cartesian displacement vectors directly (not mass-weighted). No correction needed — the eigenvectors can be used as-is, matching vibview's convention (which ORCA and Phonopy parsers already produce). `Mode.__post_init__` normalizes them as usual.

### Large files

Gaussian .log files for large systems (hundreds of atoms) can be many MB. The parser should read the file sequentially (not into memory) for the log format, or use memory-mapped string operations in Python (`.log` files are typically <100 MB even for large systems; loading into memory is acceptable).

## Rationale

- Gaussian is the most popular molecular QC package — reaching its user base is high-ROI.
- The `.log` format is stable and well-documented across versions.
- Parsing is pure Python — no new runtime dependencies.
- The ORCA parser serves as a template (similar `ParseResult` structure, same `BOHR_TO_ANGSTROM` conversion).
