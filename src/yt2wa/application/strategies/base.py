"""The interface every conversion strategy follows."""

from __future__ import annotations

from abc import ABC, abstractmethod

from yt2wa.application.dto import JobContext, StrategyOutput


class ConversionStrategy(ABC):
    """Turns a request into a file inside the job folder."""

    @abstractmethod
    def run(self, ctx: JobContext) -> StrategyOutput:
        """Download and, if needed, convert the video."""
