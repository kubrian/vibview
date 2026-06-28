# Proposal: Phonon Example System

> Replace O2 with a realistic solid-state phonon example for testing and demonstration.

---

## Problem

The `examples/` directory contains only two systems: H2O (native, molecular vibration) and O2 (native, molecular vibration). O2 is too trivial (3 degrees of freedom, no visual interest). There is no phonon example at all, making it impossible to test or demonstrate solid-state functionality like band structures, gamma-point modes, or supercell representations without first converting external data.

## Diagnosis

- `examples/o2.h5` — diatomic molecule, 1 mode, trivial for any meaningful test or showcase.
- `examples/h2o.h5` — good molecular example, but covers only the `native` parser path.
- Phonopy/ORCA workflow users must bring their own files; there's no quick "try vibview on a crystal" path.

## Proposed solution

1. **Compute** a small solid-state phonon system and store it under `examples/`:
   - **Candidate**: Diamond (C₂, 2-atom primitive cell, 6 phonon modes, high symmetry, well-known frequencies).
   - **Format**: native HDF5 (consistent with H2O).
   - **Tool**: compute with Phonopy via a (supercell) finite-displacement calculation using a small DFT setup (e.g., Quantum ESPRESSO or VASP), then convert to native format.
   - **Contents**: structure (Fd-3m, 2 atoms), phonon modes (6 eigenvalues/vectors at Gamma), optionally a path for band structure.
2. **Document** the computation steps in a comment or companion script so it's reproducible.

## Rationale

- Diamond is small (2-atom primitive cell → 6 modes), physically meaningful, and familiar to most solid-state users.
- Removing O2 eliminates a file that adds no testing value.
- A phonon example unlocks testing of diff-mode, static-mode arrows, and mode animation on a non-molecular system.
- Keeping the example reproducible prevents bitrot — if the file format changes, the generation script can be re-run.
