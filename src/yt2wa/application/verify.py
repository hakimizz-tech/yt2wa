"""Check an existing file against the WhatsApp profiles."""

from __future__ import annotations

from collections.abc import Mapping

from yt2wa.application.dto import VerifyRequest, VerifyResult
from yt2wa.domain.audio_compliance import check_audio_compliance
from yt2wa.domain.audio_profile import DEFAULT_AUDIO, AudioProfile
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.errors import UsageError
from yt2wa.domain.models import AudioFormat, MediaKind, StreamFacts, Target
from yt2wa.domain.ports import MediaProbe
from yt2wa.domain.profile import CompatProfile, profile_for

_MB = 1024 * 1024


class VerifyUseCase:
    """Run the right compliance checker on any file."""

    def __init__(
        self,
        probe: MediaProbe,
        profiles: Mapping[str, CompatProfile],
        audio_profile: AudioProfile = DEFAULT_AUDIO,
    ) -> None:
        self._probe = probe
        self._profiles = profiles
        self._audio_profile = audio_profile

    def execute(self, request: VerifyRequest) -> VerifyResult:
        """Inspect a file and report how well it matches."""
        facts = self._probe.inspect(request.path)
        if facts.vcodec is None and facts.has_audio:
            return self._verify_audio(request, facts)
        profile = profile_for(request.target, self._profiles)
        report = check_compliance(
            facts, profile, profile.size_cap_mb * _MB or None
        )
        return VerifyResult(request.path, request.target, facts, report)

    def _verify_audio(
        self, request: VerifyRequest, facts: StreamFacts
    ) -> VerifyResult:
        """Check an audio-only file."""
        if request.target is Target.STATUS:
            raise UsageError(
                "Audio files cannot be posted as a Status.",
                hint="Verify it with --target chat.",
            )
        tokens = {part.strip() for part in facts.container.split(",")}
        fmt = AudioFormat.MP3 if "mp3" in tokens else AudioFormat.M4A
        cap = self._audio_profile.size_cap_mb * _MB or None
        report = check_audio_compliance(
            facts, self._audio_profile, cap, fmt
        )
        return VerifyResult(
            request.path, request.target, facts, report, MediaKind.AUDIO
        )
