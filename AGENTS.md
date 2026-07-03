# vibview — Agent Instructions

## Task handling

When given a task, first determine if it is **small/obvious** (typo fix, mechanical rename, trivial parameter change) or **non-trivial** (new feature, bug fix, architecture change, anything touching >1 file).

- **Small/obvious:** Lightweight restatement in chat — goal, target files, acceptance criteria — then wait for approval before coding.
- **Non-trivial:** Expand to a full proposal in chat — Problem, Diagnosis, Proposed solution, Non-goals, Test plan — then wait for approval before coding.

Never go straight to code without a restatement or proposal.

## Commands

All Python invocations go through `pixi run` — never call `python` or `python3` directly.

```bash
pixi run pytest                    # all tests
pixi run pytest tests/test_X.py    # single file
pixi run pytest -k test_name       # single test
pre-commit run --all-files && pixi run pytest --cov --cov-report=term-missing   # quality gate (coverage: fail_under=80)
pixi run mkdocs serve              # local mkdocs dev server
```

**Breaking changes always allowed:** All features, APIs, CLI signatures, config keys, file formats, and data models may be changed or removed at any time without notice. No backward compatibility guarantees — this is pre-release software. Effects on the codebase should be noted in proposals but never mitigated via compat shims, deprecation warnings, or migration layers.

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

File under `docs/proposals/` following the template in `docs/task_spec.md`.

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
8. When the user approves, squash merge to the target branch and delete the
   feature branch: `git merge --squash proposal/<name> && git commit -m "<message>" && git branch -D proposal/<name>`.

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
- **One commit per task:** Before committing, inspect `git diff`. Revert scope creep, dead code, speculative abstractions.
- **Non-goals are law:** If non-goals are specified, the diff must not touch those areas — even if the code there is ugly.
- **YAGNI:** No base classes, interfaces, or abstractions introduced "just in case." A 30-line function is fine. Prefer simplest correct solution. No ABCs, hooks, or multi-version support without need. Optional parameters (dataclass fields, function/method arguments) must have a documented justification — without one they are speculative defaults.
- **No dead code:** Remove unused functions, imports, config keys. Never comment them out.
- **No silent failures:** Every error path raises or logs with context. No bare `except`, no ignored return values.

## Commits for this session

When committing the mode-and-label-semantics work, use a message describing the removal of Mode.index and the frequency-sort invariant. Proceed with a squash merge when the user approves.

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
- Test H5 files: `src/vibview/examples/water.h5`, `src/vibview/examples/diamond.h5`.
