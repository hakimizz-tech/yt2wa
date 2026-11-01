"""The main use case: turn a YouTube link into a file."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from yt2wa.application.dto import (
    ConvertRequest,
    JobContext,
    StrategyOutput,
)
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain.errors import UnsupportedSourceError
from yt2wa.domain.formats import build_format_selector, short_edge_cap
from yt2wa.domain.models import (
    BEST_RESOLUTION,
    ConversionResult,
    DryRunPlan,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.ports import Downloader, Workspace
from yt2wa.domain.profile import CompatProfile, profile_for
from yt2wa.domain.size_guard import plan_size_ladder
from yt2wa.domain.url_rules import classify_url, sanitize_filename

log = logging.getLogger(__name__)

_MB = 1024 * 1024


class ConvertUseCase:
    """Validate a request, run the right strategy and publish the file."""

    def __init__(
        self,
        downloader: Downloader,
        workspace: Workspace,
        strategies: Mapping[Target, ConversionStrategy],
        profiles: Mapping[str, CompatProfile],
    ) -> None:
        self._downloader = downloader
        self._workspace = workspace
        self._strategies = strategies
        self._profiles = profiles

    def execute(
        self,
        request: ConvertRequest,
        on_progress: ProgressCallback = ignore_progress,
    ) -> ConversionResult | DryRunPlan:
        """Run one conversion and return the published result."""
        ref = classify_url(request.url)
        if ref.kind.value == "unsupported":
            raise UnsupportedSourceError(
                "This link is not a YouTube video or Short.",
                hint="Playlists and community posts are not supported yet.",
            )
        metadata = self._downloader.probe(ref)
        profile = profile_for(request.target, self._profiles)
        cap = self._size_cap(request, profile)
        if request.dry_run:
            return self._dry_run(request, ref, metadata, profile, cap)

        job_dir = self._workspace.new_job_dir()
        log.debug("job folder: %s", job_dir)
        try:
            ctx = JobContext(
                request, ref, metadata, job_dir, profile, cap, on_progress
            )
            output = self._strategies[request.target].run(ctx)
            return self._publish(request, metadata, output)
        finally:
            self._workspace.cleanup(job_dir)

    @staticmethod
    def _size_cap(
        request: ConvertRequest, profile: CompatProfile
    ) -> int | None:
        """Return the size cap in bytes, or None when there is none."""
        if not request.target.is_shareable:
            return None
        megabytes = (
            profile.size_cap_mb
            if request.max_size_mb is None
            else request.max_size_mb
        )
        return megabytes * _MB if megabytes > 0 else None

    def _publish(
        self,
        request: ConvertRequest,
        metadata: SourceMetadata,
        output: StrategyOutput,
    ) -> ConversionResult:
        """Move the finished file into the output folder."""
        edge = output.facts.short_edge
        name = (
            f"{sanitize_filename(metadata.title)}_{edge}p"
            f"{output.path.suffix}"
        )
        final = self._workspace.publish(output.path, request.output_dir, name)

        kept = None
        if request.keep_source and output.source is not None:
            kept = self._workspace.publish(
                output.source,
                request.output_dir,
                f"{final.stem}_source{output.source.suffix}",
            )

        warnings = list(output.warnings)
        wanted = request.resolution
        if wanted != BEST_RESOLUTION and edge < wanted:
            warnings.append(
                f"Output is {edge}p (requested {wanted}p). The source was "
                "smaller or the size cap needed a lower resolution."
            )
        return ConversionResult(
            output=final,
            target=request.target,
            method=output.method,
            title=metadata.title,
            requested_resolution=wanted,
            effective_resolution=edge,
            size_bytes=final.stat().st_size,
            report=output.report,
            warnings=tuple(warnings),
            source_kept=kept,
        )

    @staticmethod
    def _dry_run(
        request: ConvertRequest,
        ref: SourceRef,
        metadata: SourceMetadata,
        profile: CompatProfile,
        cap: int | None,
    ) -> DryRunPlan:
        """Describe the plan without downloading anything."""
        choice = build_format_selector(
            request.target, request.resolution, profile.max_short_edge
        )
        lines = [
            f"Title:       {metadata.title}",
            f"Duration:    {metadata.duration_s:.0f} s",
            f"Source kind: {ref.kind.value}",
            f"Target:      {request.target.value}",
            f"yt-dlp sort: {', '.join(choice.sort)}",
        ]
        if not request.target.is_shareable:
            lines.append("Method:      download as is (no re-encode)")
            return DryRunPlan(tuple(lines))

        edge = short_edge_cap(
            request.target, request.resolution, profile.max_short_edge
        )
        lines.append(
            "Method:      decided after download (remux if the file "
            "already complies, otherwise transcode)"
        )
        lines.append(
            "Size cap:    "
            + ("none" if cap is None else f"{cap / _MB:.0f} MB")
        )
        if edge is not None and metadata.duration_s > 0:
            ladder = plan_size_ladder(
                start=edge,
                floor=profile.floor_resolution,
                duration_s=metadata.duration_s,
                cap_bytes=cap,
                audio_k=profile.audio_bitrate_k,
                min_bitrates=profile.min_video_bitrate_k,
            )
            lines.append("Size ladder (used only if a file is too big):")
            for step in ladder:
                rate = (
                    f"{step.video_bitrate_k} kbit/s"
                    if step.video_bitrate_k
                    else f"crf {profile.crf}"
                )
                lines.append(f"  - {step.resolution}p, {rate}")
        return DryRunPlan(tuple(lines))
