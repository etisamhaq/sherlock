"""Investigator base class.

An investigator gathers grounded evidence from exactly one source and returns a
Finding. It must be resilient: any failure is captured as ``Finding.error`` so
one broken source never sinks the whole investigation.
"""

from __future__ import annotations

import abc

from ..models import AlertEvent, Finding


class Investigator(abc.ABC):
    name: str = "investigator"

    def investigate(self, incident: AlertEvent) -> Finding:
        """Run the investigation, converting any exception into a Finding.error."""
        try:
            return self._investigate(incident)
        except Exception as exc:  # noqa: BLE001 - resilience is the point
            return Finding(
                investigator=self.name,
                summary=f"{self.name} failed: {exc}",
                error=str(exc),
            )

    @abc.abstractmethod
    def _investigate(self, incident: AlertEvent) -> Finding:
        raise NotImplementedError
