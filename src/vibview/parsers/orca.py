"""Parser for ORCA Hessian files (.hess)."""

from pathlib import Path

from vibview.models import Atom, Mode, ParseResult, VibData

BOHR_TO_ANGSTROM = 0.529177210544


def parse(path: Path) -> ParseResult:
    """Parse an ORCA .hess file into ParseResult.

    Args:
        path: Path to an ORCA Hessian file.

    Returns:
        A validated ParseResult containing VibData.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required sections are missing or malformed.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()

    sections = _split_sections(text)

    if "$atoms" not in sections:
        raise ValueError("No $atoms section found in .hess file")
    if "$vibrational_frequencies" not in sections:
        raise ValueError("No $vibrational_frequencies section found in .hess file")
    if "$normal_modes" not in sections:
        raise ValueError("No $normal_modes section found in .hess file")

    atoms = _parse_atoms(sections["$atoms"])
    frequencies = _parse_frequencies(sections["$vibrational_frequencies"])
    normal_modes = _parse_normal_modes(sections["$normal_modes"], len(atoms))

    modes = [
        Mode(index=i, eigenvectors=ev, frequency=freq)
        for i, (ev, freq) in enumerate(zip(normal_modes, frequencies, strict=True))
    ]

    return ParseResult(
        data=VibData(
            atoms=atoms,
            modes=modes,
            frequency_units="cm⁻¹",
        ),
    )


def _split_sections(text: str) -> dict[str, list[str]]:
    lines = text.splitlines()
    section_starts: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("$") and not stripped.startswith("$end"):
            section_starts.append((stripped, i))

    sections: dict[str, list[str]] = {}
    for k, (name, start) in enumerate(section_starts):
        end = section_starts[k + 1][1] if k + 1 < len(section_starts) else len(lines)
        sections[name] = lines[start + 1 : end]
    return sections


def _parse_atoms(lines: list[str]) -> list[Atom]:
    if not lines:
        raise ValueError("No cartesian coordinates found in .hess file")
    try:
        natoms = int(lines[0].strip())
    except ValueError:
        raise ValueError("Missing atom count in $atoms section")

    atoms: list[Atom] = []
    for i in range(1, 1 + natoms):
        if i >= len(lines):
            raise ValueError(
                f"Expected {natoms} atoms in $atoms section, found {len(atoms)}"
            )
        tokens = lines[i].split()
        if len(tokens) < 5:
            raise ValueError(f"Malformed atom line in .hess file: {lines[i]!r}")
        try:
            symbol = tokens[0]
            x = float(tokens[2]) * BOHR_TO_ANGSTROM
            y = float(tokens[3]) * BOHR_TO_ANGSTROM
            z = float(tokens[4]) * BOHR_TO_ANGSTROM
        except (ValueError, IndexError):
            raise ValueError(f"Malformed atom line in .hess file: {lines[i]!r}")
        atoms.append(Atom(symbol, [x, y, z]))

    if not atoms:
        raise ValueError("No cartesian coordinates found in .hess file")

    return atoms


def _parse_frequencies(lines: list[str]) -> list[float]:
    if not lines:
        raise ValueError("No vibrational frequencies found in .hess file")
    try:
        nfreq = int(lines[0].strip())
    except ValueError:
        raise ValueError("Missing frequency count in $vibrational_frequencies section")

    frequencies: list[float] = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        tokens = stripped.split()
        if len(tokens) < 2:
            continue
        try:
            frequencies.append(float(tokens[1]))
        except ValueError:
            raise ValueError(f"Malformed frequency line in .hess file: {line!r}")

    if not frequencies:
        raise ValueError("No vibrational frequencies found in .hess file")

    if len(frequencies) != nfreq:
        raise ValueError(f"Expected {nfreq} frequencies, found {len(frequencies)}")

    return frequencies


def _to_float(s: str) -> float:
    return float(s.replace("D", "E"))


def _parse_normal_modes(lines: list[str], n_atoms: int) -> list[list[list[float]]]:
    if not lines:
        raise ValueError("No normal modes found in .hess file")

    tokens = lines[0].split()
    if len(tokens) < 2:
        raise ValueError("Missing dimensions in $normal_modes section")
    try:
        nrows = int(tokens[0])
        ncols = int(tokens[1])
    except ValueError:
        raise ValueError(f"Invalid dimensions in $normal_modes: {lines[0]!r}")

    expected = 3 * n_atoms
    if nrows != expected or ncols != expected:
        raise ValueError(
            f"Normal modes matrix has dimensions ({nrows}, {ncols}), "
            f"expected ({expected}, {expected})"
        )

    all_data: list[list[float]] = [[] for _ in range(nrows)]
    n_cols = 0

    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            n_cols = 0
            continue

        tokens = stripped.split()
        if not tokens:
            continue

        is_header = True
        for t in tokens:
            if not (t.isdigit() or (len(t) > 1 and t[0] == "-" and t[1:].isdigit())):
                is_header = False
                break
        if is_header:
            n_cols = len(tokens)
            continue

        if n_cols > 0:
            try:
                row_idx = int(tokens[0])
                if 0 <= row_idx < nrows:
                    values = [_to_float(t) for t in tokens[1 : 1 + n_cols]]
                    all_data[row_idx].extend(values)
            except (ValueError, IndexError):
                raise ValueError(
                    f"Malformed normal-mode row in .hess file: {stripped!r}"
                )

    if not all_data or not all_data[0]:
        raise ValueError("No normal modes found in .hess file")

    n_modes = len(all_data[0])
    for i, row in enumerate(all_data):
        if len(row) != n_modes:
            raise ValueError(
                f"Incomplete normal mode matrix: row {i} has {len(row)} columns, "
                f"expected {n_modes}"
            )

    modes: list[list[list[float]]] = []
    for mi in range(n_modes):
        ev = [
            [
                all_data[ai * 3][mi],
                all_data[ai * 3 + 1][mi],
                all_data[ai * 3 + 2][mi],
            ]
            for ai in range(n_atoms)
        ]
        modes.append(ev)

    return modes
