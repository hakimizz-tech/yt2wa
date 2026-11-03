"""Run a search through several methods, best first."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from yt2wa.domain.errors import DependencyError, DomainError
from yt2wa.domain.models import (
    ProviderAttempt,
    SearchCandidate,
    SearchKind,
    SearchProviderName,
    SearchResponse,
)
from yt2wa.domain.ports import SearchProvider
from yt2wa.domain.search_providers import select_provider_chain

log = logging.getLogger(__name__)


class ChainedSearchProvider:
    """Tries each method in order until one finds candidates.

    A method is skipped when it fails or returns nothing. Naming one
    method explicitly turns the fallback off, so failures show up.
    """

    def __init__(
        self, providers: Mapping[SearchProviderName, SearchProvider]
    ) -> None:
        self._providers = providers

    def search(
        self,
        query: str,
        kind: SearchKind,
        limit: int,
        requested: SearchProviderName | None,
    ) -> SearchResponse:
        """Return candidates and how they were found."""
        explicit = requested is not None
        attempts: list[ProviderAttempt] = []
        last_error: DomainError | None = None

        for name in select_provider_chain(kind, requested):
            provider = self._providers.get(name)
            if provider is None:
                attempts.append(ProviderAttempt(name, "skipped", "not set up"))
                continue
            try:
                found: list[SearchCandidate] = provider.search(
                    query, kind, limit
                )
            except DependencyError as exc:
                if explicit:
                    raise
                log.debug("skipping %s: %s", name, exc.message)
                attempts.append(ProviderAttempt(name, "skipped", exc.message))
                last_error = exc
                continue
            except DomainError as exc:
                if explicit:
                    raise
                log.debug("%s failed: %s", name, exc.message)
                attempts.append(ProviderAttempt(name, "error", exc.message))
                last_error = exc
                continue
            if not found:
                attempts.append(ProviderAttempt(name, "empty"))
                continue
            attempts.append(ProviderAttempt(name, "ok"))
            return SearchResponse(tuple(found), name, tuple(attempts))

        # Nothing found. If any method simply had no results, that is a
        # real answer. Otherwise every method failed, so report why.
        if last_error is not None and not any(
            a.outcome == "empty" for a in attempts
        ):
            raise last_error
        return SearchResponse((), None, tuple(attempts))
