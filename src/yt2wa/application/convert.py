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
from yt2wa.domain.audio_profile import DEFAULT_AUDIO, AudioProfile
from yt2wa.domain.audio_size_guard import plan_audio_ladder
from yt2wa.domain.errors import UnsupportedSourceError, UsageError
from yt2wa.domain.formats import build_format_selector, short_edge_cap
from yt2wa.domain.models import (
    BEST_RESOLUTION,
    ConversionResult,
    DryRunPlan,
    MediaKind,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.ports import Downloader, Workspace
from yt2wa.domain.profile import CompatProfile, profile_for
from yt2wa.domain.size_guard import plan_size_ladder
from yt2wa.domain.text_rules import audio_file_stem
from yt2wa.domain.url_rules import classify_url, sanitize_filename

log = logging.getLogger(__name__)

_MB = 1024 * 1024

# Strategies are looked up by media kind and target.
PipelineKey = tuple[MediaKind, Target]


def _as_key(key: PipelineKey | Target) -> PipelineKey:
    """Accept the older Target-only keys as video pipelines."""
    return key if isinstance(key, tuple) else (MediaKind.VIDEO, key)


class ConvertUseCase:
    """Validate a request, run the right strategy and publish the file."""

    def __init__(
        self,
        downloader: Downloader,
        workspace: Workspace,
        strategies: Mapping[PipelineKey, ConversionStrategy]
        | Mapping[Target, ConversionStrategy],
        profiles: Mapping[str, CompatProfile],
        audio_profile: AudioProfile = DEFAULT_AUDIO,
    ) -> None:
        self._downloader = downloader
        self._workspace = workspace
        self._strategies: dict[PipelineKey, ConversionStrategy] = {
            _as_key(key): strategy for key, strategy in strategies.items()
        }
        self._profiles = profiles
        self._audio_profile = audio_profile

    def execute(
        self,
        request: ConvertRequest,
        on_progress: ProgressCallback = ignore_progress,
    ) -> ConversionResult | DryRunPlan:
        """Run one conversion and return the published result."""
        is_audio = request.media is MediaKind.AUDIO
        if is_audio and request.target is Target.STATUS:
            raise UsageError(
                "Audio cannot be posted as a WhatsApp Status.",
                hint="Use --target chat, or download the video instead.",
            )
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
                request,
                ref,
                metadata,
                job_dir,
                profile,
                cap,
                on_progress,
                self._audio_profile,
            )
            strategy = self._strategies[(request.media, request.target)]
            output = strategy.run(ctx)
            return self._publish(request, metadata, output)
        finally:
            self._workspace.cleanup(job_dir)

    def _size_cap(
        self, request: ConvertRequest, profile: CompatProfile
    ) -> int | None:
        """Return the size cap in bytes, or None when there is none."""
        if not request.target.is_shareable:
            return None
        default_mb = (
            self._audio_profile.size_cap_mb
            if request.media is MediaKind.AUDIO
            else profile.size_cap_mb
        )
        megabytes = (
            default_mb if request.max_size_mb is None else request.max_size_mb
        )
        return megabytes * _MB if megabytes > 0 else None

    def _publish(
        self,
        request: ConvertRequest,
        metadata: SourceMetadata,
        output: StrategyOutput,
    ) -> ConversionResult:
        """Move the finished file into the output folder."""
        is_audio = request.media is MediaKind.AUDIO
        edge = 0 if is_audio else output.facts.short_edge
        if is_audio:
            name = (
                f"{sanitize_filename(audio_file_stem(metadata))}"
                f"{output.path.suffix}"
            )
        else:
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
        if not is_audio and wanted != BEST_RESOLUTION and edge < wanted:
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
            media=request.media,
        )

    def _dry_run(
        self,
        request: ConvertRequest,
        ref: SourceRef,
        metadata: SourceMetadata,
        profile: CompatProfile,
        cap: int | None,
    ) -> DryRunPlan:
        """Describe the plan without downloading anything."""
        lines = [
            f"Title:       {metadata.title}",
            f"Duration:    {metadata.duration_s:.0f} s",
            f"Source kind: {ref.kind.value}",
            f"Target:      {request.target.value}",
            f"Media:       {request.media.value}",
        ]
        cap_text = "none" if cap is None else f"{cap / _MB:.0f} MB"
        if request.media is MediaKind.AUDIO:
            return DryRunPlan(
                tuple(
                    lines
                    + self._audio_plan(request, metadata, cap, cap_text)
                )
            )

        choice = build_format_selector(
            request.target, request.resolution, profile.max_short_edge
        )
        lines.append(f"yt-dlp sort: {', '.join(choice.sort)}")
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
        lines.append(f"Size cap:    {cap_text}")
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

    def _audio_plan(
        self,
        request: ConvertRequest,
        metadata: SourceMetadata,
        cap: int | None,
        cap_text: str,
    ) -> list[str]:
        """Describe an audio run."""
        if not request.target.is_shareable:
            return ["Method:      download the best audio as is"]
        profile = self._audio_profile
        start = request.audio_bitrate_k or profile.default_bitrate_k
        lines = [
            f"Format:      {request.audio_format.value}",
            "Method:      decided after download (remux if the audio "
            "already complies, otherwise transcode)",
            f"Size cap:    {cap_text}",
        ]
        steps = plan_audio_ladder(
            metadata.duration_s,
            cap,
            profile.ladder_bitrates_k,
            profile.min_bitrate_k,
            start,
        )
        if steps:
            lines.append("Bitrates to try: " + ", ".join(
                f"{s.bitrate_k} kbit/s" for s in steps
            ))
        else:
            lines.append("Bitrates to try: none fit the size cap")
        return lines
