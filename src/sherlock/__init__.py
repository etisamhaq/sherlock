"""Sherlock — an open-source AI agent that root-causes Kubernetes incidents.

When a K8s workload breaks, Sherlock investigates it across pod state, events,
logs, metrics, and the recent deploy that caused it, then produces a ranked,
evidence-cited root cause. See ``sherlock.orchestrator`` for the entry point.
"""

__version__ = "0.1.0"
