"""The command line: parse arguments, wire the app, run, map exit codes."""

from __future__ import annotations

import argparse
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from yt2wa import __version__
from yt2wa.application.dto import (
    ConvertRequest,
    SearchRequest,
    VerifyRequest,
)
from yt2wa.bootstrap.container import Container, build_container
from yt2wa.bootstrap.doctor import run_doctor
from yt2wa.bootstrap.logging_setup import configure_logging
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import DomainError, UsageError
from yt2wa.domain.formats import parse_resolution
from yt2wa.domain.models import (
    AudioFormat,
    DryRunPlan,
    MediaKind,
    SearchKind,
    SearchProviderName,
    Target,
    ignore_progress,
)
from yt2wa.interface.exit_codes import ExitCode, map_exception_to_exit_code
from yt2wa.interface.presenters import (
    ConsolePresenter,
    JsonPresenter,
    Presenter,
)
from yt2wa.interface.progress import ConsoleProgress

COMMANDS = ("convert", "search", "verify", "doctor", "clean")
AUDIO_BITRATES = (64, 96, 128, 192)

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


def _add_download_options(parser: argparse.ArgumentParser) -> None:
    """Add the options that control what gets downloaded."""
    parser.add_argument(
        "-t",
        "--target",
        choices=[t.value for t in Target],
        help="output intent (default: chat)",
    )
    parser.add_argument(
        "--keep-original",
        dest="target",
        action="store_const",
        const=Target.ORIGINAL.value,
        help="same as --target original",
    )
    parser.add_argument(
        "-r",
        "--resolution",
        type=_resolution_type,
        metavar="{144,240,360,480,720,1080,best}",
        help="short edge size for video (default: 480)",
    )
    parser.add_argument(
        "-x",
        "--audio",
        action="store_true",
        help="audio only",
    )
    parser.add_argument(
        "--audio-format",
        choices=[f.value for f in AudioFormat],
        help="audio format for --target chat (default: m4a)",
    )
    parser.add_argument(
        "--audio-bitrate",
        type=int,
        choices=AUDIO_BITRATES,
        metavar="{64,96,128,192}",
        help="audio bitrate in kbit/s for --target chat (default: 128)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="where to save the result (default: ./out)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        metavar="MB",
        help="size cap for chat/status (0 means no cap)",
    )
    parser.add_argument("--keep-source", action="store_true")


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
    _add_download_options(convert)
    convert.add_argument(
        "--report",
        action="store_true",
        help="print the compliance report",
    )
    convert.add_argument("--dry-run", action="store_true")

    search = sub.add_parser(
        "search",
        parents=[common],
        help="find the most likely song or video",
    )
    search.add_argument("query", nargs="+", help="what to look for")
    search.add_argument(
        "--type",
        dest="kind",
        choices=[k.value for k in SearchKind],
        default=SearchKind.ANY.value,
    )
    search.add_argument(
        "--provider",
        choices=["auto", *[p.value for p in SearchProviderName]],
        help="search method (default: auto)",
    )
    search.add_argument("--limit", type=int, help="candidates (1 to 25)")
    search.add_argument(
        "--detail",
        action="store_true",
        help="fetch full metadata for the best match",
    )
    search.add_argument(
        "--download",
        action="store_true",
        help="download the best match (needs enough confidence)",
    )
    search.add_argument(
        "--min-confidence",
        type=float,
        metavar="0-1",
        help="with --download (default: 0.6)",
    )
    search.add_argument(
        "--pick",
        type=int,
        metavar="N",
        help="with --download: use result N (1 is the best match)",
    )
    _add_download_options(search)

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


def _check_audio_options(args: argparse.Namespace) -> None:
    """Reject option combinations that make no sense."""
    if not args.audio:
        if args.audio_format is not None or args.audio_bitrate is not None:
            raise UsageError(
                "--audio-format and --audio-bitrate need --audio.",
            )
    elif args.target == Target.STATUS.value:
        raise UsageError(
            "Audio cannot be posted as a WhatsApp Status.",
            hint="Use --target chat, or download the video instead.",
        )


def _notes(args: argparse.Namespace, presenter: Presenter) -> None:
    """Explain options that do nothing in this combination."""
    if not args.audio:
        return
    if args.resolution is not None:
        presenter.note("Resolution is ignored for audio.")
    if args.target == Target.ORIGINAL.value and (
        args.audio_format is not None or args.audio_bitrate is not None
    ):
        presenter.note(
            "--audio-format and --audio-bitrate are ignored with "
            "--target original (the audio is kept as it is)."
        )


def _build_request(
    args: argparse.Namespace, settings: Settings, url: str, dry_run: bool
) -> ConvertRequest:
    """Turn parsed options into a conversion request."""
    return ConvertRequest(
        url=url,
        target=Target(args.target or settings.default_target),
        resolution=(
            settings.default_resolution
            if args.resolution is None
            else args.resolution
        ),
        output_dir=args.output_dir or settings.output_dir,
        max_size_mb=args.max_size,
        keep_source=args.keep_source,
        dry_run=dry_run,
        media=MediaKind.AUDIO if args.audio else MediaKind.VIDEO,
        audio_format=AudioFormat(args.audio_format or settings.audio_format),
        audio_bitrate_k=args.audio_bitrate,
    )


def _convert(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the convert command."""
    _check_audio_options(args)
    _notes(args, presenter)
    request = _build_request(args, container.settings, args.url, args.dry_run)
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


_DOWNLOAD_FLAGS = (
    "target",
    "resolution",
    "audio_format",
    "audio_bitrate",
    "output_dir",
    "max_size",
)


def _check_search_options(args: argparse.Namespace) -> None:
    """Make sure download-only options are used with --download."""
    if args.download:
        _check_audio_options(args)
        return
    stray = [
        name for name in _DOWNLOAD_FLAGS if getattr(args, name) is not None
    ]
    stray += [
        name for name in ("audio", "keep_source") if getattr(args, name)
    ]
    if args.pick is not None:
        stray.append("pick")
    if args.min_confidence is not None:
        stray.append("min_confidence")
    if stray:
        names = ", ".join("--" + n.replace("_", "-") for n in stray)
        raise UsageError(
            f"{names} can only be used together with --download.",
            hint="Add --download, or remove those options.",
        )


def _search(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the search command."""
    _check_search_options(args)
    settings = container.settings
    if args.provider is None:
        provider = settings.search_provider
    elif args.provider == "auto":
        provider = None
    else:
        provider = SearchProviderName(args.provider)

    download = None
    if args.download:
        _notes(args, presenter)
        download = _build_request(args, settings, "", dry_run=False)
    request = SearchRequest(
        query=" ".join(args.query),
        kind=SearchKind(args.kind),
        limit=args.limit if args.limit is not None else settings.search_limit,
        provider=provider,
        detail=args.detail,
        min_confidence=(
            settings.min_confidence
            if args.min_confidence is None
            else args.min_confidence
        ),
        download=download,
        pick=args.pick,
    )
    quiet = args.json or args.quiet or download is None
    progress = ignore_progress if quiet else ConsoleProgress()
    try:
        outcome = container.search.execute(request, progress)
    finally:
        if isinstance(progress, ConsoleProgress):
            progress.finish()
    presenter.search(outcome)
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
    "search": _search,
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
        JsonPresenter()
        if args.json
        else ConsolePresenter(quiet=args.quiet, verbose=args.verbose > 0)
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
