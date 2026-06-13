"""Per-investigation budget guardrails.

Two hard ceilings protect cost and prevent runaway agents on noisy alert storms:
a token budget (output tokens spent on the LLM) and a wall-clock budget. The
orchestrator checks the budget before the expensive synthesis step.
"""

from __future__ import annotations

import time


class BudgetExceeded(RuntimeError):
    """Raised when an investigation exceeds its token or time budget."""


class Budget:
    def __init__(
        self,
        token_budget: int = 20_000,
        time_budget_seconds: float = 180.0,
        *,
        clock=time.monotonic,
    ) -> None:
        self.token_budget = token_budget
        self.time_budget_seconds = time_budget_seconds
        self._clock = clock
        self._start = clock()
        self.tokens_spent = 0

    def add_tokens(self, n: int) -> None:
        self.tokens_spent += max(0, int(n))

    def tokens_remaining(self) -> int:
        return max(0, self.token_budget - self.tokens_spent)

    def elapsed_seconds(self) -> float:
        return self._clock() - self._start

    def time_remaining(self) -> float:
        return max(0.0, self.time_budget_seconds - self.elapsed_seconds())

    def check(self) -> None:
        """Raise BudgetExceeded if either ceiling has been hit."""
        if self.tokens_spent >= self.token_budget:
            raise BudgetExceeded(
                f"token budget exhausted: {self.tokens_spent}/{self.token_budget}"
            )
        elapsed = self.elapsed_seconds()  # read the clock once
        if elapsed >= self.time_budget_seconds:
            raise BudgetExceeded(
                f"time budget exhausted: {elapsed:.1f}s/{self.time_budget_seconds:.0f}s"
            )
