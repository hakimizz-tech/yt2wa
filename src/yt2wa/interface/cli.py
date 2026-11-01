"""The command line: parse arguments, wire the app, run, map exit codes."""

from __future__ import annotations

import argparse
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from yt2wa import __version__
from yt2wa.application.dto import ConvertRequest, VerifyRequest
from yt2wa.bootstrap.container import Container, build_container
from yt2wa.bootstrap.doctor import run_doctor
from yt2wa.bootstrap.logging_setup import configure_logging
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import DomainError, UsageError
from yt2wa.domain.formats import parse_resolution
from yt2wa.domain.models import DryRunPlan, Target, ignore_progress
from yt2wa.interface.exit_codes import ExitCode, map_exception_to_exit_code
from yt2wa.interface.presenters import (
    ConsolePresenter,
    JsonPresenter,
    Presenter,
)
from yt2wa.interface.progress import ConsoleProgress

COMMANDS = ("convert", "verify", "doctor", "clean")

NOTICE = (
    "Legal note: downloading may break YouTube's Terms of Service or "
    "copyright law. Use this tool only for content you own, have permission "
    "to use, or that is licensed for reuse."
)


def _resolution_type(text: str) -> int:
    """Argparse type for --resolution."""
    try:
        return parse_resolution(text)
    except UsageError as exc:
        raise argparse.ArgumentTypeError(exc.message) from exc


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output")
    common.add_argument("-v", "--verbose", action="count", default=0)
    common.add_argument("-q", "--quiet", action="store_true")

    parser = argparse.ArgumentParser(
        prog="yt2wa",
        description="Download YouTube videos and make them WhatsApp ready.",
        epilog=NOTICE,
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser(
        "convert", parents=[common], help="download and convert a video"
    )
    convert.add_argument("url", help="YouTube video or Short link")
    convert.add_argument(
        "-t",
        "--target",
        choices=[t.value for t in Target],
        help="output intent (default: chat)",
    )
    convert.add_argument(
        "--keep-original",
        dest="target",
        action="store_const",
        const=Target.ORIGINAL.value,
        help="same as --target original",
    )
    convert.add_argument(
        "-r",
        "--resolution",
        type=_resolution_type,
        metavar="{144,240,360,480,720,1080,best}",
        help="short edge size (default: 480)",
    )
    convert.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        metavar="PATH",
        help="where to save the result (default: ./out)",
    )
    convert.add_argument(
        "--max-size",
        type=int,
        metavar="MB",
        help="override size cap for chat/status (default: 16 MB; 0 means no cap)",
    )
    convert.add_argument(
        "--report",
        action="store_true",
        help="print the compliance report",
    )
    convert.add_argument(
        "--keep-source",
        action="store_true",
        help="keep the downloaded source file",
    )
    convert.add_argument(
        "--dry-run",
        action="store_true",
        help="show the plan and ffmpeg argv only",
    )

    verify = sub.add_parser(
        "verify", parents=[common], help="check a file against the profile"
    )
    verify.add_argument("file", type=Path)
    verify.add_argument(
        "-t",
        "--target",
        choices=[Target.CHAT.value, Target.STATUS.value],
        default=Target.CHAT.value,
    )

    sub.add_parser(
        "doctor", parents=[common], help="check ffmpeg, ffprobe and yt-dlp"
    )

    clean = sub.add_parser(
        "clean", parents=[common], help="remove old scratch folders"
    )
    clean.add_argument(
        "--hours",
        type=float,
        default=24.0,
        metavar="HOURS",
        help="remove scratch folders older than this (default: 24)",
    )
    return parser


def with_default_command(argv: Sequence[str]) -> list[str]:
    """Insert 'convert' when the user typed only a link and options."""
    args = list(argv)
    if args and args[0] not in COMMANDS and args[0] not in (
        "-h",
        "--help",
        "--version",
    ):
        return ["convert", *args]
    return args


def _convert(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the convert command."""
    settings = container.settings
    request = ConvertRequest(
        url=args.url,
        target=Target(args.target or settings.default_target),
        resolution=(
            settings.default_resolution
            if args.resolution is None
            else args.resolution
        ),
        output_dir=args.output_dir or settings.output_dir,
        max_size_mb=args.max_size,
        keep_source=args.keep_source,
        dry_run=args.dry_run,
    )
    quiet = args.json or args.quiet
    progress = ignore_progress if quiet else ConsoleProgress()
    try:
        outcome = container.convert.execute(request, progress)
    finally:
        if isinstance(progress, ConsoleProgress):
            progress.finish()
    if isinstance(outcome, DryRunPlan):
        presenter.dry_run(outcome)
    else:
        presenter.result(outcome, args.report)
    return ExitCode.OK


def _verify(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the verify command."""
    result = container.verify.execute(
        VerifyRequest(args.file, Target(args.target))
    )
    presenter.verify(result)
    return ExitCode.OK if result.report.ok else ExitCode.CONSTRAINT


def _doctor(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the doctor command."""
    checks = run_doctor(container.settings)
    presenter.doctor(checks)
    return ExitCode.OK if all(c.ok for c in checks) else ExitCode.DEPENDENCY


def _clean(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the clean command."""
    old = container.workspace.stale_jobs(args.hours * 3600)
    for path in old:
        container.workspace.cleanup(path)
    presenter.cleaned(old)
    return ExitCode.OK


_HANDLERS = {
    "convert": _convert,
    "verify": _verify,
    "doctor": _doctor,
    "clean": _clean,
}


def _raise_interrupt(signum: int, frame: FrameType | None) -> None:
    """Turn SIGTERM into Ctrl+C so cleanup code runs."""
    raise KeyboardInterrupt


def _log_level(args: argparse.Namespace, settings: Settings) -> str:
    """Pick the log level from flags and settings."""
    if args.quiet:
        return "ERROR"
    if args.verbose:
        return "DEBUG"
    return settings.log_level


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool and return the exit code."""
    raw = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(with_default_command(raw))
    presenter: Presenter = (
        JsonPresenter() if args.json else ConsolePresenter(quiet=args.quiet)
    )
    try:
        settings = Settings.from_env()
        configure_logging(_log_level(args, settings), settings.log_format)
        container = build_container(settings)
        signal.signal(signal.SIGTERM, _raise_interrupt)
        code = _HANDLERS[args.command](args, container, presenter)
    except DomainError as exc:
        presenter.error(exc)
        return int(map_exception_to_exit_code(exc))
    except KeyboardInterrupt:
        presenter.interrupted()
        return int(ExitCode.INTERRUPTED)
    return int(code)
