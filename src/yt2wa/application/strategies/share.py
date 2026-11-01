"""The ``chat`` and ``status`` targets: make a WhatsApp friendly file."""

from __future__ import annotations

from pathlib import Path

from yt2wa.application.dto import JobContext, StrategyOutput
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain import compliance as c
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.decision import choose_best_candidate, decide_path
from yt2wa.domain.errors import NonCompliantOutputError, SizeCapError
from yt2wa.domain.ffmpeg_args import FfmpegPlan, build_ffmpeg_args
from yt2wa.domain.formats import build_format_selector, short_edge_cap
from yt2wa.domain.models import Candidate, LadderStep, Method, StreamFacts
from yt2wa.domain.ports import Downloader, MediaProbe, Transcoder
from yt2wa.domain.size_guard import plan_size_ladder


class ShareStrategy(ConversionStrategy):
    """Download, then remux or re-encode until the file passes."""

    def __init__(
        self,
        downloader: Downloader,
        probe: MediaProbe,
        transcoder: Transcoder,
        ffmpeg_bin: str = "ffmpeg",
        threads: int = 0,
    ) -> None:
        self._downloader = downloader
        self._probe = probe
        self._transcoder = transcoder
        self._ffmpeg_bin = ffmpeg_bin
        self._threads = threads
        self._attempts = 0

    def run(self, ctx: JobContext) -> StrategyOutput:
        """Produce the smallest compliant file, or raise."""
        request, profile = ctx.request, ctx.profile
        cap = short_edge_cap(
            request.target, request.resolution, profile.max_short_edge
        )
        assert cap is not None  # Shareable targets always have a cap.

        choice = build_format_selector(
            request.target, request.resolution, profile.max_short_edge
        )
        source = self._downloader.download(
            ctx.ref, choice, ctx.job_dir / "source", ctx.on_progress
        )
        facts = self._probe.inspect(source)
        report = check_compliance(
            facts, profile, ctx.size_cap_bytes, short_cap=cap
        )
        decision = decide_path(report)

        out_dir = ctx.job_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[Candidate] = []

        if decision.method is Method.REMUX:
            remux = self._attempt(
                ctx, source, facts, cap, out_dir, Method.REMUX, None
            )
            candidates.append(remux)

        if not any(cand.report.ok for cand in candidates):
            duration = facts.duration_s or ctx.metadata.duration_s
            ladder = plan_size_ladder(
                start=min(cap, facts.short_edge),
                floor=profile.floor_resolution,
                duration_s=duration,
                cap_bytes=ctx.size_cap_bytes,
                audio_k=profile.audio_bitrate_k,
                min_bitrates=profile.min_video_bitrate_k,
            )
            for step in ladder:
                cand = self._attempt(
                    ctx, source, facts, cap, out_dir, Method.TRANSCODE, step
                )
                self._reject_non_size_errors(cand)
                candidates.append(cand)
                if cand.report.ok:
                    break

        best = choose_best_candidate(candidates)
        if best is None:
            raise SizeCapError(
                "Could not fit the video under the size limit.",
                hint=(
                    "Try a lower --resolution, raise --max-size, or send "
                    "the file as a Document."
                ),
            )
        return StrategyOutput(
            path=best.path,
            method=best.method,
            facts=self._probe.inspect(best.path),
            report=best.report,
            warnings=tuple(self._warnings(best, facts, cap)),
            source=source,
        )

    def _attempt(
        self,
        ctx: JobContext,
        source: Path,
        facts: StreamFacts,
        cap: int,
        out_dir: Path,
        method: Method,
        step: LadderStep | None,
    ) -> Candidate:
        """Run ffmpeg once and check the file it produced."""
        self._attempts += 1
        output = out_dir / f"candidate_{self._attempts}.mp4"
        plan = FfmpegPlan(
            source=source,
            output=output,
            method=method,
            facts=facts,
            profile=ctx.profile,
            short_cap=step.resolution if step else cap,
            step=step,
            threads=self._threads,
            ffmpeg_bin=self._ffmpeg_bin,
        )
        self._transcoder.run(
            build_ffmpeg_args(plan),
            facts.duration_s or ctx.metadata.duration_s,
            ctx.on_progress,
        )
        out_facts = self._probe.inspect(output)
        report = check_compliance(
            out_facts,
            ctx.profile,
            ctx.size_cap_bytes,
            short_cap=cap,
            source_aspect=facts.aspect,
        )
        return Candidate(output, report, out_facts.size_bytes, method)

    @staticmethod
    def _reject_non_size_errors(candidate: Candidate) -> None:
        """Stop when a re-encode failed for a reason other than size."""
        problems = [
            f"{r.name} (expected {r.expected}, got {r.actual})"
            for r in candidate.report.errors
            if r.name != c.FILE_SIZE
        ]
        if problems:
            raise NonCompliantOutputError(
                "The converted file fails checks: " + "; ".join(problems),
                hint="Run with -vv and report the ffmpeg command.",
            )

    @staticmethod
    def _warnings(
        best: Candidate, source: StreamFacts, cap: int
    ) -> list[str]:
        """Collect advice and notes about the chosen file."""
        notes = [
            f"{r.name}: expected {r.expected}, got {r.actual}"
            for r in best.report.warnings
        ]
        if source.short_edge < cap:
            notes.append(
                f"The source is only {source.short_edge}p, so it was not "
                "upscaled."
            )
        return notes
