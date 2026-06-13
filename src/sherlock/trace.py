"""Investigation tracing for trust + debugging ("show me what the agent did").

Every step an investigation takes is recorded with a monotonic sequence number
and an optional data payload. The trace is attached to the Investigation result
and can be replayed or surfaced to a skeptical engineer.
"""

from __future__ import annotations

from typing import Any


class Trace:
    def __init__(self) -> None:
        self._steps: list[dict[str, Any]] = []

    def add(self, step: str, **data: Any) -> None:
        self._steps.append({"seq": len(self._steps), "step": step, **data})

    def to_list(self) -> list[dict[str, Any]]:
        return list(self._steps)

    def __len__(self) -> int:
        return len(self._steps)
