"""CLI entrypoint and argument parsing."""

import argparse
import importlib.metadata
import sys
from importlib.resources import files as resource_files
from pathlib import Path

from vibview.config import USER_CONFIG_PATH, Config
from vibview.core import Structure
from vibview.parsers import PARSER_NAMES, make_qpoint_loader
from vibview.parsers import parse as parse_file
from vibview.parsers.native import dump as dump_native
from vibview.renderers.vispy_renderer import VispyViewer


def _add_input_args(parser: argparse.ArgumentParser) -> None:
    """Add shared input arguments: file, type, mode, qpoint, config."""
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        default=None,
        help="Input file (default: bundled water example)",
    )
    parser.add_argument(
        "type",
        nargs="?",
        default="native",
        choices=sorted(PARSER_NAMES),
        help="Input file format (default: native)",
    )

    # --- data selection ---
    g = parser.add_argument_group("Data selection")
    g.add_argument(
        "--example",
        "-e",
        type=str,
        help="Load bundled example by name (e.g. 'water', 'diamond')",
    )
    g.add_argument(
        "--mode",
        "-m",
        type=int,
        default=0,
        help="Vibrational mode index (0-based, default: 0)",
    )
    g.add_argument(
        "--qpoint",
        "-q",
        type=int,
        default=0,
        help="Q-point index (0-based, default: 0)",
    )

    # --- config ---
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        help="Session config YAML — merged with defaults, overrides ~/.config/vibview/config.yaml",
    )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vibrational mode visualization tool for computational chemistry.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"vibview {importlib.metadata.version('vibview')}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="Commands",
        metavar="<command>",
    )

    # --- init-config ---
    p = subparsers.add_parser(
        "init-config",
        help="Write a commented default config to ~/.config/vibview/config.yaml",
    )
    p.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing config file without prompting",
    )

    # --- view ---
    p = subparsers.add_parser("view", help="Launch interactive viewer")
    _add_input_args(p)

    # --- export ---
    p = subparsers.add_parser(
        "export",
        help="Export animation to PNG sequence, GIF, or MP4",
    )
    _add_input_args(p)
    p.add_argument(
        "--format",
        required=True,
        choices=["png", "gif", "mp4"],
        help="Output format",
    )
    p.add_argument(
        "--name",
        type=str,
        required=True,
        help="Output name root: file stem for gif/mp4, path prefix for png",
    )

    # --- convert ---
    p = subparsers.add_parser(
        "convert",
        help="Convert parsed data to native HDF5 format",
    )
    _add_input_args(p)
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output HDF5 path",
    )

    return parser


def _run_init_config(args: argparse.Namespace) -> int:
    config_text = resource_files("vibview.data").joinpath("defaults.yaml").read_text()
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if USER_CONFIG_PATH.exists() and not args.force:
        print(
            f"{USER_CONFIG_PATH} already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1
    USER_CONFIG_PATH.write_text(config_text)
    print(f"Wrote default config to {USER_CONFIG_PATH}", file=sys.stderr)
    return 0


def _load_structure(args: argparse.Namespace) -> tuple[Config, Structure, str | None]:
    """Load config, parse file, and build Structure.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Tuple of (config, structure, source_path).

    Raises:
        FileNotFoundError: If the input file does not exist.
        ValueError: If --example and input file are both provided,
            if the format is unsupported, if exporting a non-native
            file, or if --example is set to an unknown name.
    """
    config = Config.load(args.config)

    if args.example and args.file is not None:
        raise ValueError("--example and input file are mutually exclusive")

    if args.example:
        ex_path = resource_files("vibview.examples").joinpath(f"{args.example}.h5")
        if not ex_path.exists():
            raise ValueError(f"Unknown example '{args.example}'")
        file = ex_path
        file_type = "native"
    elif args.file is None:
        if args.command in ("export", "convert"):
            raise ValueError(f"'{args.command}' requires an input file")
        file = resource_files("vibview.examples").joinpath("water.h5")
        file_type = "native"
    else:
        file = args.file
        file_type = args.type

    result = parse_file(file, file_type, args.qpoint)

    if args.command == "view" and file_type != "native":
        print(
            f"Warning: '{file}' is in '{file_type}' format. "
            "For faster subsequent loads, convert it using: "
            f"vibview convert '{file}' '{file_type}' -o <name>.h5",
            file=sys.stderr,
        )
    elif args.command == "export" and file_type != "native":
        raise ValueError(
            f"Exporting '{file}' requires native format. "
            "Please convert it first using: "
            f"vibview convert '{file}' '{file_type}' -o <name>.h5"
        )

    qpoint_loader = make_qpoint_loader(result)
    structure = Structure(result.data, qpoint_loader=qpoint_loader)
    if args.qpoint != 0:
        structure.switch_qpoint(args.qpoint)

    return config, structure, result.source


def main(argv: list[str] | None = None) -> int:
    """Entry point for the vibview CLI.

    Parses CLI arguments, loads configuration, builds the structure,
    and dispatches to the appropriate subcommand.

    Args:
        argv: Optional argument list (for testing). Defaults to ``sys.argv``.

    Returns:
        Exit code (0 on success, 1 on error).
    """
    if argv is None:
        argv = sys.argv[1:]
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "init-config":
        return _run_init_config(args)

    try:
        config, structure, source_path = _load_structure(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    supercell = config.display.supercell

    if args.command == "view":
        viewer = VispyViewer(
            structure,
            config=config,
            mode_type=config.animation.default_mode,
            mode_index=args.mode,
            qpoint_index=args.qpoint,
            create_window=True,
            supercell=supercell,
            source_path=source_path,
        )
        viewer.run()

    elif args.command == "export":
        viewer = VispyViewer(
            structure,
            config=config,
            mode_type=config.animation.default_mode,
            mode_index=args.mode,
            qpoint_index=args.qpoint,
            create_window=False,
            supercell=supercell,
            source_path=source_path,
        )
        viewer.export_animation(
            format=args.format,
            name=args.name,
            cycles=config.export.cycles,
            progress_callback=None,
        )

    elif args.command == "convert":
        dump_native(
            structure.data,
            args.output,
            qpoint_loader=structure.qpoint_loader,
            qpoint_index=structure.qpoint_index,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
