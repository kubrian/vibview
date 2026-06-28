# vibview — Agent Instructions

## Commands

All Python invocations go through `pixi run` — never call `python` or `python3` directly.

```bash
pixi run pytest                    # all tests
pixi run pytest tests/test_X.py    # single file
pixi run pytest -k test_name       # single test
pre-commit run --all-files && pixi run pytest   # quality gate (coverage: fail_under=80)
pixi run mkdocs serve              # local mkdocs dev server
```

**Pre-release:** backward compatibility is not a concern. Files/data formats may change freely.

## Entrypoint

`vibview.main:main` — argparse CLI. Subcommands: `view`, `export`, `convert`, `init-config`.
App entry: `VispyViewer(structure, config, mode_index, qpoint_index, supercell)`.
Export mode passes `create_window=False`.

## Config cascade

`defaults.yaml` → `~/.config/vibview/config.yaml` → `--config` session file.
Generate a commented template with `vibview init-config`.

## Three modes

| mode                | visual                                                    |
| ------------------- | --------------------------------------------------------- |
| `animate` (default) | animated oscillation                                      |
| `static`            | orange arrows (shaft + cone, `shading=<quality-derived>`) |
| `overlay`           | wireframes: eq=blue, disp=semi-transparent red            |

Mode, amplitude, quality, axis visibility, and supercell are configured via YAML only — not CLI flags.

## Proposals

File under `docs/proposals/` with format: title `# Proposal: <name>`, one-line summary `> <...>`, `---`, then sections `## Problem` → `## Diagnosis` → `## Proposed solution` → `## Rationale`.

When the user says "work on <proposal>" or "implement <proposal>", follow the
implementation workflow below automatically without asking for approval first.

Implementation workflow (strict order):

1. Review the proposal and plan the implementation.
2. Create a dedicated feature branch: `git checkout -b proposal/<name>`.
3. Update `docs/design.md` if the proposal introduces a user-facing
   capability, architectural decision, or design rationale.
4. Implement on that branch — **never on `main`**.
5. Delete the proposal file (folded into the implementation commit).
6. Run the quality gate: `pre-commit run --all-files && pixi run pytest`.
7. Commit with a conventional message and suggest user review/merge.

## Conventions

- **Google-style docstrings:** Use Google-style (`Args:`, `Returns:`, `Raises:`)
  for all public functions, methods, and classes. Private helpers may omit
  docstrings if their purpose is obvious from the name.
- **Docs-first:** Update docstrings first — they are the source of truth for
  `docs/api.md` (auto-generated via mkdocstrings). Configuration keys and their
  defaults live in `src/vibview/data/defaults.yaml` with inline comments; keep
  that file in sync with the `Config` dataclasses (test-enforced).
  `docs/design.md` uses use-case prose, not syntax reference. Keeping
  documentation current is part of every change, not a separate task.
- **Test-first:** Write the failing test before implementation.
- **Conventional commits:** `type: description` (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- **YAGNI:** Prefer simplest correct solution. No ABCs, hooks, or multi-version support without need.
- **No dead code:** Remove unused functions, imports, config keys. Never comment them out.
- **No silent failures:** Every error path raises or logs with context. No bare `except`, no ignored return values.

## Parser formats

`--format` must be one of: `native`, `orca`, `phonopy`. Registered in `parsers/__init__.py::PARSERS`.
Parsers produce `VibData` → `Structure`.

## Architecture

- `core.py` never imports from `renderers/` or `parsers/`.
- View mode entry via `_apply_mode_state()` (overlays + animation), called from both init and `switch_mode()`.
- Amplitude set per mode _before_ building visuals (set amplitude → build → apply).

## Environment

Managed via **pixi** (conda-forge, linux-64, Python == 3.10.\*).
Deps in `pyproject.toml`: numpy, pyyaml, vispy, pyqt6, h5py, Pillow, imageio.

## Renderer test quirks

- `_mock_qt_window` (autouse) patches `VibviewWindow`.
- `_patch_vispy` patches SceneCanvas, Tube, Sphere, Mesh, etc.
- `_MockMesh` must accept `shading=None` kwarg if changed.
- `_make_structure(atoms, modes)` builds `Structure` from atom/mode lists.
- Test H5 file: `src/vibview/examples/h2o.h5`.
