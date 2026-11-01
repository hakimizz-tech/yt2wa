"""The ``original`` target: keep the video as downloaded."""

from __future__ import annotations

from yt2wa.application.dto import JobContext, StrategyOutput
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.formats import build_format_selector
from yt2wa.domain.models import Method, Target
from yt2wa.domain.ports import Downloader, MediaProbe


class OriginalStrategy(ConversionStrategy):
    """Download the best phone-friendly streams without re-encoding."""

    def __init__(self, downloader: Downloader, probe: MediaProbe) -> None:
        self._downloader = downloader
        self._probe = probe

    def run(self, ctx: JobContext) -> StrategyOutput:
        """Download the video and describe what we got."""
        choice = build_format_selector(
            Target.ORIGINAL,
            ctx.request.resolution,
            ctx.profile.max_short_edge,
        )
        path = self._downloader.download(
            ctx.ref, choice, ctx.job_dir / "source", ctx.on_progress
        )
        facts = self._probe.inspect(path)

        # The report is informational only. Nothing is enforced here.
        report = check_compliance(facts, ctx.profile)
        warnings = []
        if not report.ok:
            warnings.append(
                f"Saved as {facts.container.split(',')[0]} with "
                f"{facts.vcodec or 'no'} video. It may not play in every "
                "app and WhatsApp may reject it. Use --target chat to share."
            )
        return StrategyOutput(
            path=path,
            method=Method.DOWNLOAD,
            facts=facts,
            report=report,
            warnings=tuple(warnings),
        )
