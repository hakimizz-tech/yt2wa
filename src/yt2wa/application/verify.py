"""Check an existing file against the WhatsApp profile."""

from __future__ import annotations

from collections.abc import Mapping

from yt2wa.application.dto import VerifyRequest, VerifyResult
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.ports import MediaProbe
from yt2wa.domain.profile import CompatProfile, profile_for

_MB = 1024 * 1024


class VerifyUseCase:
    """Run the compliance checker on any file."""

    def __init__(
        self, probe: MediaProbe, profiles: Mapping[str, CompatProfile]
    ) -> None:
        self._probe = probe
        self._profiles = profiles

    def execute(self, request: VerifyRequest) -> VerifyResult:
        """Inspect a file and report how well it matches."""
        profile = profile_for(request.target, self._profiles)
        facts = self._probe.inspect(request.path)
        report = check_compliance(
            facts, profile, profile.size_cap_mb * _MB or None
        )
        return VerifyResult(request.path, request.target, facts, report)
