"""The search use case: find the most likely song or video."""

from __future__ import annotations

import logging
from dataclasses import replace

from yt2wa.application.convert import ConvertUseCase
from yt2wa.application.dto import SearchOutcome, SearchRequest
from yt2wa.domain.errors import DomainError, NotFoundError, UsageError
from yt2wa.domain.models import (
    ConversionResult,
    ProgressCallback,
    ScoredCandidate,
    SearchResult,
    SourceKind,
    SourceMetadata,
    SourceRef,
    ignore_progress,
)
from yt2wa.domain.ports import Downloader, SearchGateway
from yt2wa.domain.ranking import rank_candidates
from yt2wa.domain.search_providers import MAX_LIMIT
from yt2wa.domain.text_rules import clean_query

log = logging.getLogger(__name__)


class SearchUseCase:
    """Search, rank, optionally enrich and optionally download."""

    def __init__(
        self,
        gateway: SearchGateway,
        downloader: Downloader,
        convert: ConvertUseCase,
    ) -> None:
        self._gateway = gateway
        self._downloader = downloader
        self._convert = convert

    def execute(
        self,
        request: SearchRequest,
        on_progress: ProgressCallback = ignore_progress,
    ) -> SearchOutcome:
        """Run a search and return the ranked result."""
        query = clean_query(request.query)
        if not query:
            raise UsageError("The search text is empty.")
        limit = max(1, min(request.limit, MAX_LIMIT))

        response = self._gateway.search(
            query, request.kind, limit, request.provider
        )
        if not response.candidates:
            tried = ", ".join(a.provider.value for a in response.attempts)
            raise NotFoundError(
                f"Nothing found for '{query}'.",
                hint=f"Methods tried: {tried or 'none'}.",
            )
        ranked = rank_candidates(query, response.candidates, request.kind)
        result = replace(
            ranked, provider=response.provider, attempts=response.attempts
        )

        notes: list[str] = []
        detail = None
        if request.detail and result.best is not None:
            detail = self._describe(result.best, notes)

        conversion = None
        if request.download is not None:
            chosen = self._choose(request, result)
            outcome = self._convert.execute(
                replace(request.download, url=chosen.candidate.url),
                on_progress,
            )
            if isinstance(outcome, ConversionResult):
                conversion = outcome
        return SearchOutcome(result, detail, conversion, tuple(notes))

    def _describe(
        self, best: ScoredCandidate, notes: list[str]
    ) -> SourceMetadata | None:
        """Fetch full metadata for the best match. Never fatal."""
        ref = SourceRef(
            best.candidate.url, SourceKind.VIDEO, best.candidate.video_id
        )
        try:
            return self._downloader.probe(ref)
        except DomainError as exc:
            notes.append(f"Could not fetch full details: {exc.message}")
            return None

    @staticmethod
    def _choose(
        request: SearchRequest, result: SearchResult
    ) -> ScoredCandidate:
        """Pick what to download, refusing weak or unclear matches."""
        assert result.best is not None
        if request.pick is not None:
            everything = (result.best, *result.alternates)
            if not 1 <= request.pick <= len(everything):
                raise UsageError(
                    f"--pick {request.pick} is out of range "
                    f"(1 to {len(everything)})."
                )
            return everything[request.pick - 1]
        if result.confidence < request.min_confidence:
            raise NotFoundError(
                f"Best match confidence {result.confidence:.2f} is below "
                f"{request.min_confidence:.2f}.",
                hint="Refine the search, lower --min-confidence, or use "
                "--pick N.",
            )
        if result.ambiguous:
            raise NotFoundError(
                "Several results match about equally well.",
                hint="Choose one with --pick N (1 is the best match).",
            )
        return result.best
