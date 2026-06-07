"""Base verifier types."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


@dataclass
class VerifyOutcome:
    passed: bool
    score: float
    reason: str


class VerifierBase(BaseMetric):
    """Abstract base for all verifiers. Implements deepeval.BaseMetric."""

    def __init__(self, *, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self._score: float = 0.0
        self._reason: str = ""

    @property
    def score(self) -> float:
        return self._score

    @score.setter
    def score(self, value: float) -> None:
        self._score = value

    @property
    def reason(self) -> str:
        return self._reason

    @reason.setter
    def reason(self, value: str) -> None:
        self._reason = value

    @property
    def success(self) -> bool:
        return self._score >= self.threshold

    @abstractmethod
    def measure(self, test_case: LLMTestCase) -> float: ...  # type: ignore[override]

    async def a_measure(self, test_case: LLMTestCase) -> float:
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.measure, test_case)

    def is_successful(self) -> bool:
        return self.success
