"""The ``original`` target for audio: keep the audio as downloaded."""

from __future__ import annotations

from yt2wa.application.dto import JobContext, StrategyOutput
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain.audio_compliance import check_audio_compliance
from yt2wa.domain.audio_profile import DEFAULT_AUDIO
from yt2wa.domain.formats import build_audio_format_selector
from yt2wa.domain.models import Method
from yt2wa.domain.ports import Downloader, MediaProbe


class AudioOriginalStrategy(ConversionStrategy):
    """Download the best audio stream without re-encoding."""

    def __init__(self, downloader: Downloader, probe: MediaProbe) -> None:
        self._downloader = downloader
        self._probe = probe

    def run(self, ctx: JobContext) -> StrategyOutput:
        """Download the audio and describe what we got."""
        path = self._downloader.download(
            ctx.ref,
            build_audio_format_selector(None),
            ctx.job_dir / "source",
            ctx.on_progress,
        )
        facts = self._probe.inspect(path)

        # The report is informational only. Nothing is enforced here.
        report = check_audio_compliance(
            facts, ctx.audio_profile or DEFAULT_AUDIO
        )
        warnings = []
        if not report.ok:
            warnings.append(
                f"Saved as {facts.acodec or 'unknown'} audio in "
                f"{facts.container.split(',')[0]}. It may not play in every "
                "app and WhatsApp may reject it. Use --audio without "
                "--keep-original to share it."
            )
        return StrategyOutput(
            path=path,
            method=Method.DOWNLOAD,
            facts=facts,
            report=report,
            warnings=tuple(warnings),
        )
