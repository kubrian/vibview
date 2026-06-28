"""Parser registry and dispatch.

Usage:
    from vibview.parsers import parse
    data = parse(path, format="native")
"""

from collections.abc import Callable
from functools import partial
from pathlib import Path

from vibview.models import Mode, ParseResult

from . import native, orca, phonopy

PARSERS: dict[str, Callable[..., ParseResult]] = {
    "native": native.parse,
    "orca": orca.parse,
    "phonopy": partial(phonopy.parse, qpoint_index=0),
}


def parse(path: Path, format: str) -> ParseResult:
    """Parse a file using the named format parser.

    Args:
        path: Path to the input file.
        format: Parser format name (e.g. "native", "orca").

    Returns:
        A ParseResult containing the validated VibData.

    Raises:
        ValueError: If the format is not recognised.
    """
    if format not in PARSERS:
        available = ", ".join(sorted(PARSERS))
        raise ValueError(f"Unknown format: {format!r}. Available formats: {available}")
    return PARSERS[format](path)


def make_qpoint_loader(result: ParseResult) -> Callable[[int], list[Mode]] | None:
    """Create a cached callable that loads a single q-point's modes on demand.

    The returned loader caches each q-point after the first load, so
    revisiting the same q-point is instant. Returns None if the result
    has no loader.
    """
    raw_loader = result.qpoint_loader
    if raw_loader is None or result.data.qpoints is None:
        return None

    cache: dict[int, list[Mode]] = {}

    def _cached(qi: int) -> list[Mode]:
        if qi not in cache:
            cache[qi] = raw_loader(qi)
        return cache[qi]

    return _cached
