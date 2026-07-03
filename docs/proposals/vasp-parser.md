# Proposal: VASP Parser

> Parse VASP OUTCAR and vasprun.xml files for solid-state phonon visualization.

---

## Problem

VASP is the dominant DFT code for solid-state phonon calculations — used in conjunction with Phonopy or directly (via finite differences or DFPT). vibview currently supports Phonopy YAML output, but not VASP's native output formats. Users who run VASP + Phonopy are already covered by the phonopy parser, but users who:

- Run VASP with IBRION=5/6 (direct DFPT frequencies in OUTCAR), or
- Use phonopy via `phonopy --vasp` output (vasprun.xml), or
- Want to inspect intermediate results before running Phonopy post-processing

cannot load their data directly into vibview.

## Diagnosis

- VASP's `OUTCAR` contains phonon frequencies and displacements when `IBRION=5/6` or `IBRION=8` is used.
- `vasprun.xml` is the structured XML output that Phonopy itself consumes.
- Neither format is currently handled by any parser.
- Both formats are molecular/crystal-capable (VASP always has a lattice).

### OUTCAR format (IBRION=5/6)

Relevant sections:

```
 Eigenvectors after division by SQRT(mass)
  (...)
   X         Y         Z           X         Y         Z
  1.23      4.56      7.89        0.12      0.34      0.56
  9.87      6.54      3.21        0.98      0.76      0.54
```

Position/frequency block:

```
 Eigenvalues after division by SQRT(mass) (h/kg)
  1 f  =   123.456789 THz
  2 f  =   456.789012 THz
```

Atoms section (POTCAR info):

```
 ions per type = 2 1 ...
```

Lattice and positions are in the CONTCAR/POSCAR-style header block.

### vasprun.xml format

A structured XML file with tags:

```xml
<modeling>
  <structure>
    <crystal>
      <varray name="basis"> ... </varray>
    </crystal>
    <varray name="positions"> ... </varray>
  </structure>
  <calculation>
    <varray name="forces"> ... </varray>
  </calculation>
  <calculation>
    <eigenvalues>
      <array name="phonon_dos"> ... </array>
    </eigenvalues>
  </calculation>
</modeling>
```

## Proposed solution

Add `src/vibview/parsers/vasp.py` supporting both `OUTCAR` (text) and `vasprun.xml` (XML) formats.

### OUTCAR parser

**Extraction logic**:

1. **Atoms and lattice**: Parse the POSCAR-style header block (lattice vectors in direct/reciprocal, atom types and counts, selective dynamics flag). This is the same format used by the CONTCAR/POSCAR file.

2. **Frequencies**: Find the section starting with `"Eigenvalues after division by SQRT(mass)"`. Parse the frequency table (index, f/ f/i designation, value in THz). Negative/imagnary frequencies are flagged with `f/i`.

   Convert THz → cm⁻¹ using: `1 THz = 33.356 cm⁻¹`.

3. **Eigenvectors**: Find the section starting with `"Eigenvectors after division by SQRT(mass)"`. The matrix is organized as blocks — one block per mode, each block containing `(n_atoms × 3)` displacement values. Values are in Å²/amu (mass-weighted Cartesian).

   **Mass de-weighting**: Each atom has a mass from the POTCAR section. Divide each atom's 3-component displacement by `sqrt(mass)` to recover Cartesian displacements, matching vibview's convention.

4. **Lattice**: VASP uses direct lattice vectors in the header. Read `a1, a2, a3` vectors.

5. **Positions**: Read from the POSCAR block (direct or Cartesian coordinates; convert if direct by multiplying with the lattice matrix).

### vasprun.xml parser

**Extraction logic**:

1. Use Python's `xml.etree.ElementTree` (stdlib — no new dependencies).
2. Parse `<structure>` for lattice vectors and atomic positions.
3. Parse `<calculation>` sections for forces (optional, for validation).
4. Find phonon specific section (present when `IBRION=5/6` or when running `phonopy --vasp`):
   - Look for `<set>` with `comment="phonon eigenvalues"` or similar.
   - Parse frequency values + eigenvector arrays.
5. Check for `<varray name="phonon_eigenvectors">` blocks.

**Complication**: The vasprun.xml structure varies significantly depending on how it was generated:

- VASP's native DFPT output (IBRION=8) has a different XML structure than phonopy-processed vasprun.xml.
- Phonopy writes its own data into vasprun.xml when `--vasp` is used.

**Decision**: Support the **phonopy-generated** vasprun.xml format first (most common use case). Add native VASP DFPT support as a follow-up.

### Registration

Add a single `"vasp"` entry to `PARSERS`:

```python
"vasp": partial(vasp.parse, fmt="auto")
```

The `fmt` parameter can be `"auto"` (try OUTCAR, fall back to vasprun.xml), `"outcar"`, or `"xml"`.

### Tests

- Create a minimal OUTCAR fixture with 2 atoms and 6 modes (diamond Γ-point).
- Create a minimal vasprun.xml fixture for the same system.
- Test atom/position parsing, frequency extraction, eigenvector de-weighting.
- Test imaginary frequency flagging.
- Test error handling: missing sections, wrong IBRION value.

## Difficulties and considerations

### Format instability

VASP's OUTCAR format has changed across versions (VASP 5.x vs 6.x). Key risks:

- The "Eigenvalues after division by SQRT(mass)" header may be absent in some IBRION modes (only present with `IBRION=5/6`, not `IBRION=8`).
- The `f/i` imaginary frequency marker is version-dependent (VASP 6.x uses `f` for real, `f/i` for imaginary; VASP 5.x may differ).
- POSCAR/CONTCAR format is stable across VASP 5.x–6.x.

**Mitigation**: Target VASP 6.x first; document version range. Use regex-based, lenient parsing with clear error messages.

### Mass de-weighting

VASP stores mass-weighted eigenvectors (like Phonopy). The de-weighting formula is the same as in `phonopy.py:40`:

```python
re + 1j*im / sqrt_mass
```

Extract masses from the POTCAR header (each atom type's mass is listed). This is fragile — POTCAR headers are not machine-friendly.

**Alternative**: Use standard atomic masses based on element symbols (already available in `Config.elements[key].mass`). This is more reliable and avoids POTCAR parsing. Standard masses are close enough to the pseudopotential masses for visualization purposes.

**Decision**: Use standard masses from the element config. Log a warning if a user-configured mass differs significantly from the POTCAR-reported mass.

### vasprun.xml size

vasprun.xml files can be very large (hundreds of MB for large systems with many ionic steps). For phonon data, the file contains only the final (or few) ionic steps, so typical size is <100 MB.

**Mitigation**: Use `xml.etree.ElementTree.iterparse()` for streaming parse — don't load the entire DOM into memory.

### Lazy loading

VASP output contains only one q-point (Γ, unless phonopy-processed). Multi-q-point data requires phonopy post-processing. The parser should:

- For OUTCAR: produce a single-q-point `ParseResult` (Γ-point, `q=[[0,0,0]]`).
- For vasprun.xml (phonopy-processed): produce multi-q-point `ParseResult` with `qpoint_loader`, matching the phonopy parser's behavior.

### Unit conversion

VASP frequencies are in THz. The standard conversion to cm⁻¹ is:

```
ω[cm⁻¹] = ω[THz] × 33.356
```

The parser should store frequencies in cm⁻¹ (consistent with ORCA and the native HDF5 format). Store `frequency_units="cm⁻¹"`.

## Rationale

- VASP is the dominant solid-state DFT code — adding VASP support covers the largest user base.
- The OUTCAR path provides zero-dependency access to DFPT phonon results.
- The vasprun.xml path aligns with the existing Phonopy ecosystem.
- No new runtime dependencies (stdlib XML parser).
