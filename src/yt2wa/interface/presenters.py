"""Turn results and errors into text for people or machines."""

from __future__ import annotations

import json
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from yt2wa.application.dto import VerifyResult
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
    ) -> None:
        self._quiet = quiet
        self._out = out or sys.stdout
        self._err = err or sys.stderr

    def _say(self, tag: str, text: str) -> None:
        print(f"[{tag}] {text}", file=self._err)

    def result(self, result: ConversionResult, show_report: bool) -> None:
        """Show a finished conversion."""
        print(result.output, file=self._out)
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
    "format_size",
    "to_jsonable",
]
