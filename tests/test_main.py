import pytest

from vibview.main import create_parser


class TestCreateParser:
    def test_no_subcommand_fails(self):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["input.h5", "native"])

    def test_view_invalid_type(self):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["view", "input.h5", "vasp"])

    def test_view_no_file_uses_defaults(self):
        parser = create_parser()
        args = parser.parse_args(["view"])
        assert args.command == "view"
        assert args.file is None
        assert args.type == "native"
        assert args.mode == 0
        assert args.qpoint == 0

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (["view", "input.h5", "native"], 0),
            (["view", "input.h5", "native", "--mode", "2"], 2),
        ],
    )
    def test_mode_flag(self, args, expected):
        parser = create_parser()
        result = parser.parse_args(args)
        assert result.mode == expected

    def test_qpoint(self):
        parser = create_parser()
        args = parser.parse_args(["view", "input.h5", "native", "--qpoint", "3"])
        assert args.qpoint == 3

    def test_config(self):
        parser = create_parser()
        args = parser.parse_args(
            ["view", "input.h5", "native", "--config", "session.yaml"]
        )
        assert args.config.suffix == ".yaml"

    def test_short_flags(self):
        parser = create_parser()
        args = parser.parse_args(
            [
                "view",
                "input.h5",
                "native",
                "-i",
                "1",
                "-c",
                "cfg.yaml",
            ]
        )
        assert args.mode == 1
        assert args.config.suffix == ".yaml"

    def test_init_config_force_flag(self):
        parser = create_parser()
        args = parser.parse_args(["init-config", "--force"])
        assert args.command == "init-config"
        assert args.force is True

    def test_export_subcommand(self):
        parser = create_parser()
        args = parser.parse_args(
            ["export", "input.h5", "native", "--format", "gif", "--name", "out"]
        )
        assert args.command == "export"
        assert args.format == "gif"
        assert args.name == "out"

    def test_export_format_mandatory(self):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["export", "input.h5", "native"])

    def test_export_format_choices(self):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                ["export", "input.h5", "native", "--format", "webp", "--name", "out"]
            )

    def test_export_format_mp4(self):
        parser = create_parser()
        args = parser.parse_args(
            ["export", "input.h5", "native", "--format", "mp4", "--name", "vid"]
        )
        assert args.format == "mp4"
        assert args.name == "vid"

    def test_convert_subcommand(self):
        parser = create_parser()
        args = parser.parse_args(["convert", "input.h5", "native", "-o", "out.h5"])
        assert args.command == "convert"
        assert str(args.output) == "out.h5"

    def test_convert_requires_output(self):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["convert", "input.h5", "native"])
