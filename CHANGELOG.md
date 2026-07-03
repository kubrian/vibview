# Changelog

## v0.2.0 — 2026-07-03

### Breaking

- **Removed `Mode.index`** — modes are identified by frequency-sorted position (0-based internally, 1-indexed in the UI). Frequency is now mandatory.
- **Removed all optional/default arguments** across the codebase — every config field, function parameter, and dataclass field is now required or has an explicit sentinel.
- **`frequency_units` is now required** on `VibData`.
- **`VibData` XOR invariant** — exactly one of `modes` or `qpoints` must be present (molecular XOR crystal).

### Features

- **Editable mode labels** — inline editing for native HDF5 files, Save Labels button, q-point switch confirmation dialog.
- **Frequency-sort invariant** — modes auto-sorted ascending by frequency at load time.
- **Config-driven camera** — orthographic default, configurable pose (azimuth, elevation, roll, distance), HUD overlay.
- **`Color` dataclass** with hex-string validation at config-load time.
- **`--example` CLI flag** — launch viewer with bundled examples (`--example diamond`, `--example water`).
- **Cross-platform support** — pixi matrix for linux-64, osx-64, osx-arm64, win-64; CI runs all four.
- **Diamond phonon example** (`examples/diamond.h5`) — 2-atom primitive cell, 6 modes.

### Fixes

- Changed short CLI flags: `-i` → `-m` for `--mode`, added `-q` for `--qpoint`.
- Added `imageio-ffmpeg` as explicit pip dependency.
- Added `--cov` flags so `coverage.xml` is generated in CI.
- Fixed `detect_bonds` KeyError for unknown element symbols (fallback radius).

### Chores

- `.gitignore` simplified to `scratch/` catch-all.
- Pre-release warning banner added to README.
- Pre-commit hooks added to pixi environment.
- Parser proposals added (VASP, Gaussian, CASTEP, band-structure viewer).
- Task specification template (`docs/task_spec.md`).

## v0.1.0 — 2026-06-28

- Initial release.
- Three visualization modes: animated oscillation, static displacement arrows, wireframe overlay.
- GUI viewer with mode selector, drag-to-rotate, scroll-to-zoom.
- Export to PNG sequence, GIF, and MP4.
- Format conversion from ORCA `.hess` and phonopy YAML to native HDF5.
- Solid-state capable: multi-q-point crystal data with lattice rendering.
- YAML configuration cascade (defaults → user → session → CLI).
