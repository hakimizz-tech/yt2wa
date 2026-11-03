"""The composition root: the one place that creates and wires objects."""

from __future__ import annotations

from dataclasses import dataclass

from yt2wa.application.convert import ConvertUseCase
from yt2wa.application.search import SearchUseCase
from yt2wa.application.search_chain import ChainedSearchProvider
from yt2wa.application.strategies.audio_original import AudioOriginalStrategy
from yt2wa.application.strategies.audio_share import AudioShareStrategy
from yt2wa.application.strategies.original import OriginalStrategy
from yt2wa.application.strategies.share import ShareStrategy
from yt2wa.application.verify import VerifyUseCase
from yt2wa.bootstrap.profiles import load_audio_profile, load_profiles
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.audio_profile import AudioProfile
from yt2wa.domain.models import MediaKind, SearchProviderName, Target
from yt2wa.domain.ports import SearchProvider
from yt2wa.domain.profile import CompatProfile
from yt2wa.infrastructure.ffmpeg_transcoder import FfmpegTranscoder
from yt2wa.infrastructure.ffprobe_probe import FfprobeMediaProbe
from yt2wa.infrastructure.local_workspace import LocalWorkspace
from yt2wa.infrastructure.ytdlp_downloader import YtDlpDownloader
from yt2wa.infrastructure.ytdlp_search import YtDlpSearchProvider
from yt2wa.infrastructure.ytmusicapi_search import YtMusicApiSearchProvider


@dataclass(frozen=True)
class Container:
    """The wired application."""

    settings: Settings
    profiles: dict[str, CompatProfile]
    audio_profile: AudioProfile
    workspace: LocalWorkspace
    convert: ConvertUseCase
    verify: VerifyUseCase
    search: SearchUseCase


def build_container(settings: Settings) -> Container:
    """Create every adapter and use case from the settings."""
    profiles = load_profiles(settings)
    audio_profile = load_audio_profile(settings)
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
    audio_share = AudioShareStrategy(
        downloader,
        probe,
        transcoder,
        ffmpeg_bin=settings.ffmpeg_bin,
        threads=settings.ffmpeg_threads,
    )
    strategies = {
        (MediaKind.VIDEO, Target.ORIGINAL): OriginalStrategy(
            downloader, probe
        ),
        (MediaKind.VIDEO, Target.CHAT): share,
        (MediaKind.VIDEO, Target.STATUS): share,
        (MediaKind.AUDIO, Target.ORIGINAL): AudioOriginalStrategy(
            downloader, probe
        ),
        (MediaKind.AUDIO, Target.CHAT): audio_share,
    }
    convert = ConvertUseCase(
        downloader, workspace, strategies, profiles, audio_profile
    )

    # Search methods. The chain tries the best one first (see ADR-0012).
    providers: dict[SearchProviderName, SearchProvider] = {
        SearchProviderName.YTMUSICAPI: YtMusicApiSearchProvider(),
        SearchProviderName.YTMUSIC_URL: YtDlpSearchProvider(
            SearchProviderName.YTMUSIC_URL,
            settings.net_retries,
            settings.cookies_file,
        ),
        SearchProviderName.YTSEARCH: YtDlpSearchProvider(
            SearchProviderName.YTSEARCH,
            settings.net_retries,
            settings.cookies_file,
        ),
    }
    return Container(
        settings=settings,
        profiles=profiles,
        audio_profile=audio_profile,
        workspace=workspace,
        convert=convert,
        verify=VerifyUseCase(probe, profiles, audio_profile),
        search=SearchUseCase(
            ChainedSearchProvider(providers), downloader, convert
        ),
    )
