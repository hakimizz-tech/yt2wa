"""The ``chat`` target for audio: make a WhatsApp friendly audio file."""

from __future__ import annotations

from pathlib import Path

from yt2wa.application.dto import JobContext, StrategyOutput
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain import compliance as c
from yt2wa.domain.audio_compliance import (
    check_audio_compliance,
    decide_audio_path,
)
from yt2wa.domain.audio_ffmpeg_args import AudioPlan, build_audio_ffmpeg_args
from yt2wa.domain.audio_profile import DEFAULT_AUDIO, AudioProfile
from yt2wa.domain.audio_size_guard import AudioStep, plan_audio_ladder
from yt2wa.domain.decision import choose_best_candidate
from yt2wa.domain.errors import NonCompliantOutputError, SizeCapError
from yt2wa.domain.formats import build_audio_format_selector
from yt2wa.domain.models import AudioFormat, Candidate, Method, StreamFacts
from yt2wa.domain.ports import Downloader, MediaProbe, Transcoder
from yt2wa.domain.text_rules import audio_tags


class AudioShareStrategy(ConversionStrategy):
    """Download audio, then remux or re-encode until the file passes."""

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
        """Produce a compliant audio file, or raise."""
        profile = ctx.audio_profile or DEFAULT_AUDIO
        fmt = ctx.request.audio_format
        bitrate = ctx.request.audio_bitrate_k or profile.default_bitrate_k

        source = self._downloader.download(
            ctx.ref,
            build_audio_format_selector(fmt),
            ctx.job_dir / "source",
            ctx.on_progress,
        )
        facts = self._probe.inspect(source)
        if not facts.has_audio:
            raise NonCompliantOutputError(
                "The download has no audio stream.",
                hint="Try again, or report the link.",
            )
        report = check_audio_compliance(
            facts, profile, ctx.size_cap_bytes, fmt, bitrate
        )
        decision = decide_audio_path(report)

        out_dir = ctx.job_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        tags = audio_tags(ctx.metadata)
        candidates: list[Candidate] = []

        if decision.method is Method.REMUX:
            candidates.append(
                self._attempt(
                    ctx, profile, source, facts, out_dir, tags,
                    Method.REMUX, AudioStep(bitrate),
                )  # fmt: skip
            )

        if not any(cand.report.ok for cand in candidates):
            duration = facts.duration_s or ctx.metadata.duration_s
            ladder = plan_audio_ladder(
                duration,
                ctx.size_cap_bytes,
                profile.ladder_bitrates_k,
                profile.min_bitrate_k,
                bitrate,
            )
            if not ladder:
                raise SizeCapError(
                    "This audio is too long to fit under the size limit.",
                    hint=(
                        "Raise --max-size, or send the file as a Document."
                    ),
                )
            for step in ladder:
                cand = self._attempt(
                    ctx, profile, source, facts, out_dir, tags,
                    Method.TRANSCODE, step,
                )  # fmt: skip
                self._reject_non_size_errors(cand)
                candidates.append(cand)
                if cand.report.ok:
                    break

        best = choose_best_candidate(candidates)
        if best is None:
            raise SizeCapError(
                "Could not fit the audio under the size limit.",
                hint="Raise --max-size, or send the file as a Document.",
            )
        return StrategyOutput(
            path=best.path,
            method=best.method,
            facts=self._probe.inspect(best.path),
            report=best.report,
            warnings=tuple(
                f"{r.name}: expected {r.expected}, got {r.actual}"
                for r in best.report.warnings
            ),
            source=source,
        )

    def _attempt(
        self,
        ctx: JobContext,
        profile: AudioProfile,
        source: Path,
        facts: StreamFacts,
        out_dir: Path,
        tags: dict[str, str],
        method: Method,
        step: AudioStep,
    ) -> Candidate:
        """Run ffmpeg once and check the file it produced."""
        self._attempts += 1
        fmt: AudioFormat = ctx.request.audio_format
        output = out_dir / f"candidate_{self._attempts}.{fmt.value}"
        plan = AudioPlan(
            source=source,
            output=output,
            method=method,
            facts=facts,
            profile=profile,
            audio_format=fmt,
            bitrate_k=step.bitrate_k,
            tags=tags,
            threads=self._threads,
            ffmpeg_bin=self._ffmpeg_bin,
        )
        self._transcoder.run(
            build_audio_ffmpeg_args(plan),
            facts.duration_s or ctx.metadata.duration_s,
            ctx.on_progress,
        )
        out_facts = self._probe.inspect(output)
        report = check_audio_compliance(
            out_facts, profile, ctx.size_cap_bytes, fmt, step.bitrate_k
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
                "The converted audio fails checks: " + "; ".join(problems),
                hint="Run with -vv and report the ffmpeg command.",
            )
