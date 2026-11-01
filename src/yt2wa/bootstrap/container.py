"""The composition root: the one place that creates and wires objects."""

from __future__ import annotations

from dataclasses import dataclass

from yt2wa.application.convert import ConvertUseCase
from yt2wa.application.strategies.original import OriginalStrategy
from yt2wa.application.strategies.share import ShareStrategy
from yt2wa.application.verify import VerifyUseCase
from yt2wa.bootstrap.profiles import load_profiles
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.models import Target
from yt2wa.domain.profile import CompatProfile
from yt2wa.infrastructure.ffmpeg_transcoder import FfmpegTranscoder
from yt2wa.infrastructure.ffprobe_probe import FfprobeMediaProbe
from yt2wa.infrastructure.local_workspace import LocalWorkspace
from yt2wa.infrastructure.ytdlp_downloader import YtDlpDownloader


@dataclass(frozen=True)
class Container:
    """The wired application."""

    settings: Settings
    profiles: dict[str, CompatProfile]
    workspace: LocalWorkspace
    convert: ConvertUseCase
    verify: VerifyUseCase


def build_container(settings: Settings) -> Container:
    """Create every adapter and use case from the settings."""
    profiles = load_profiles(settings)
    downloader = YtDlpDownloader(
        retries=settings.net_retries, cookies_file=settings.cookies_file
    )
    probe = FfprobeMediaProbe(settings.ffprobe_bin)
    transcoder = FfmpegTranscoder()
    workspace = LocalWorkspace(settings.work_dir)

    share = ShareStrategy(
        downloader,
        probe,
        transcoder,
        ffmpeg_bin=settings.ffmpeg_bin,
        threads=settings.ffmpeg_threads,
    )
    strategies = {
        Target.ORIGINAL: OriginalStrategy(downloader, probe),
        Target.CHAT: share,
        Target.STATUS: share,
    }
    return Container(
        settings=settings,
        profiles=profiles,
        workspace=workspace,
        convert=ConvertUseCase(downloader, workspace, strategies, profiles),
        verify=VerifyUseCase(probe, profiles),
    )
