from yt2wa.domain.errors import SizeCapError, UsageError
from yt2wa.interface.cli import build_parser, with_default_command
from yt2wa.interface.exit_codes import ExitCode, map_exception_to_exit_code


def test_bare_link_runs_convert():
    assert with_default_command(["https://youtu.be/x"])[0] == "convert"


def test_known_command_is_kept():
    assert with_default_command(["doctor"]) == ["doctor"]


def test_keep_original_sets_the_target():
    args = build_parser().parse_args(
        ["convert", "u", "--keep-original", "-r", "best"]
    )
    assert args.target == "original"
    assert args.resolution == 0


def test_convert_option_defaults_remain_settings_driven():
    args = build_parser().parse_args(["convert", "u"])
    assert args.target is None
    assert args.resolution is None
    assert args.output_dir is None
    assert args.max_size is None
    assert args.report is False
    assert args.keep_source is False
    assert args.dry_run is False


def test_help_describes_convert_options(capsys):
    try:
        build_parser().parse_args(["convert", "--help"])
    except SystemExit:
        pass
    help_text = capsys.readouterr().out
    assert "where to save the result (default: ./out)" in help_text
    assert "print the compliance report" in help_text
    assert "keep the downloaded source file" in help_text
    assert "show the plan and ffmpeg argv only" in help_text


def test_help_describes_clean_hours(capsys):
    try:
        build_parser().parse_args(["clean", "--help"])
    except SystemExit:
        pass
    assert "remove scratch folders older than this (default: 24)" in (
        capsys.readouterr().out
    )


def test_exit_codes():
    assert map_exception_to_exit_code(UsageError("x")) == ExitCode.USAGE
    assert (
        map_exception_to_exit_code(SizeCapError("x")) == ExitCode.CONSTRAINT
    )
    assert map_exception_to_exit_code(ValueError("x")) == ExitCode.GENERAL
