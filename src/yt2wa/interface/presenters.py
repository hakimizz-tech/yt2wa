"""Turn results and errors into text for people or machines."""

from __future__ import annotations

import json
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from yt2wa.application.dto import SearchOutcome, VerifyResult
from yt2wa.bootstrap.doctor import DoctorCheck
from yt2wa.domain.errors import DomainError
from yt2wa.domain.models import (
    ComplianceReport,
    ConversionResult,
    DryRunPlan,
    Method,
    Severity,
    Target,
)

_METHOD_TEXT = {
    Method.DOWNLOAD: "downloaded as is, no re-encode",
    Method.REMUX: "remuxed, no re-encode",
    Method.TRANSCODE: "re-encoded",
}


def format_clock(seconds: float) -> str:
    """Return a length such as '3:42' (or '1:02:03')."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_count(number: int | None) -> str:
    """Return a view count such as '612.3M'."""
    if number is None:
        return "? views"
    steps = ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K"))
    for limit, suffix in steps:
        if number >= limit:
            return f"{number / limit:.1f}{suffix} views"
    return f"{number} views"


def format_size(size_bytes: int) -> str:
    """Return a size such as '7.9 MB'."""
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def to_jsonable(value: Any) -> Any:
    """Convert results into plain data that json can write."""
    if isinstance(value, ComplianceReport):
        return {
            "ok": value.ok,
            "checks": [to_jsonable(r) for r in value.results],
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_jsonable(getattr(value, f.name)) for f in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value


class ConsolePresenter:
    """Print for people. The result path goes to stdout, the rest to stderr."""

    def __init__(
        self,
        quiet: bool = False,
        out: TextIO | None = None,
        err: TextIO | None = None,
        verbose: bool = False,
    ) -> None:
        self._quiet = quiet
        self._out = out or sys.stdout
        self._err = err or sys.stderr
        self._verbose = verbose

    def _say(self, tag: str, text: str) -> None:
        print(f"[{tag}] {text}", file=self._err)

    def note(self, text: str) -> None:
        """Show a short note about how the options were applied."""
        if not self._quiet:
            self._say("note", text)

    def result(self, result: ConversionResult, show_report: bool) -> None:
        """Show a finished conversion."""
        print(result.output, file=self._out)
        self._result_info(result, show_report)

    def _result_info(
        self, result: ConversionResult, show_report: bool
    ) -> None:
        """Show the details of a conversion on stderr."""
        if self._quiet:
            return
        self._say(
            "ok",
            f"Saved {result.output} ({format_size(result.size_bytes)}, "
            f"{_METHOD_TEXT[result.method]})",
        )
        if result.report is not None and result.target.is_shareable:
            total = len(result.report.results)
            passed = sum(1 for r in result.report.results if r.passed)
            self._say("ok", f"Compliance: {passed}/{total} checks passed")
        for warning in result.warnings:
            self._say("warn", warning)
        if result.target.is_shareable:
            self._say(
                "info",
                "WhatsApp may still re-compress media. Send the file as a "
                "Document to keep its quality.",
            )
        if result.source_kept:
            self._say("info", f"Source kept at {result.source_kept}")
        if show_report and result.report is not None:
            self._report(result.report)

    def dry_run(self, plan: DryRunPlan) -> None:
        """Show what a run would do."""
        for line in plan.lines:
            print(line, file=self._out)

    def search(self, outcome: SearchOutcome) -> None:
        """Show the best match, the alternates and any download."""
        result = outcome.result
        best = result.best
        if outcome.conversion is not None:
            print(outcome.conversion.output, file=self._out)
        elif best is not None:
            print(best.candidate.url, file=self._out)
        if self._quiet or best is None:
            return

        name = f"{best.artist} - {best.track}" if best.artist else best.track
        cand = best.candidate
        provider = result.provider.value if result.provider else "unknown"
        self._say(
            "ok",
            f"Best match (confidence {result.confidence:.2f}) via {provider}",
        )
        print(f"       {name}", file=self._err)
        print(
            f"       {cand.channel or 'unknown channel'} | "
            f"{format_clock(cand.duration_s)} | "
            f"{format_count(cand.view_count)} | {cand.url}",
            file=self._err,
        )
        print(f"       why: {'; '.join(best.reasons)}", file=self._err)
        if outcome.detail is not None:
            self._detail(outcome)
        if result.ambiguous:
            self._say(
                "warn",
                "Several results match about equally well. Use --pick N "
                "to choose.",
            )
        if result.alternates:
            self._say("info", "Alternates:")
            for number, alt in enumerate(result.alternates, start=2):
                who = (
                    f"{alt.artist} - {alt.track}" if alt.artist else alt.track
                )
                print(
                    f"       {number}. {who}  {alt.score:.2f}  "
                    f"({alt.candidate.channel or '?'}, "
                    f"{format_clock(alt.candidate.duration_s)})",
                    file=self._err,
                )
        if self._verbose or len(result.attempts) > 1:
            tried = ", ".join(
                f"{a.provider.value} ({a.outcome}"
                f"{': ' + a.detail if a.detail else ''})"
                for a in result.attempts
            )
            self._say("info", f"Methods tried: {tried}")
        for note in outcome.notes:
            self._say("warn", note)
        if outcome.conversion is not None:
            self._result_info(outcome.conversion, False)

    def _detail(self, outcome: SearchOutcome) -> None:
        """Show the extra metadata fetched with --detail."""
        meta = outcome.detail
        assert meta is not None
        rows = [
            ("track", meta.track),
            ("artist", meta.artist),
            ("album", meta.album),
            ("uploaded", meta.upload_date),
            ("uploader", meta.uploader),
        ]
        for label, value in rows:
            if value:
                print(f"       {label}: {value}", file=self._err)

    def verify(self, result: VerifyResult) -> None:
        """Show the result of checking a file."""
        self._report(result.report)
        verdict = "matches" if result.report.ok else "does NOT match"
        self._say(
            "ok" if result.report.ok else "fail",
            f"{result.path.name} {verdict} the {result.target.value} "
            "profile.",
        )

    def doctor(self, checks: list[DoctorCheck]) -> None:
        """Show the environment checks."""
        for check in checks:
            tag = "ok" if check.ok else "fail"
            print(f"[{tag}] {check.name}: {check.detail}", file=self._err)

    def cleaned(self, paths: list[Path]) -> None:
        """Show which folders were removed."""
        self._say("ok", f"Removed {len(paths)} old job folder(s).")

    def error(self, exc: DomainError) -> None:
        """Show an error and its hint."""
        self._say("error", exc.message)
        if exc.hint:
            self._say("hint", exc.hint)

    def interrupted(self) -> None:
        """Show that the user stopped the run."""
        self._say("error", "Interrupted.")

    def _report(self, report: ComplianceReport) -> None:
        """Print every check on its own line."""
        for r in report.results:
            if r.passed:
                label = "PASS"
            elif r.severity is Severity.WARNING:
                label = "WARN"
            else:
                label = "FAIL"
            detail = r.actual if r.passed else (
                f"{r.actual} (expected {r.expected})"
            )
            print(f"  {label}  {r.name}: {detail}", file=self._err)


class JsonPresenter:
    """Print machine readable JSON on stdout."""

    def __init__(self, out: TextIO | None = None) -> None:
        self._out = out or sys.stdout

    def _dump(self, payload: Any) -> None:
        print(json.dumps(to_jsonable(payload), indent=2), file=self._out)

    def result(self, result: ConversionResult, show_report: bool) -> None:
        """Write a finished conversion."""
        self._dump(result)

    def dry_run(self, plan: DryRunPlan) -> None:
        """Write the dry run plan."""
        self._dump({"plan": plan.lines})

    def note(self, text: str) -> None:
        """Ignore notes: they are not part of the JSON output."""

    def search(self, outcome: SearchOutcome) -> None:
        """Write the search outcome."""
        self._dump(outcome)

    def verify(self, result: VerifyResult) -> None:
        """Write the result of checking a file."""
        self._dump(result)

    def doctor(self, checks: list[DoctorCheck]) -> None:
        """Write the environment checks."""
        self._dump({"checks": checks})

    def cleaned(self, paths: list[Path]) -> None:
        """Write which folders were removed."""
        self._dump({"removed": paths})

    def error(self, exc: DomainError) -> None:
        """Write an error."""
        self._dump({"error": exc.message, "hint": exc.hint})

    def interrupted(self) -> None:
        """Write that the run was interrupted."""
        self._dump({"error": "interrupted"})


Presenter = ConsolePresenter | JsonPresenter

__all__ = [
    "ConsolePresenter",
    "JsonPresenter",
    "Presenter",
    "Target",
    "format_clock",
    "format_count",
    "format_size",
    "to_jsonable",
]
