"""Runtime wiring: build clients/LLM from Config and run an investigation.

Single source of truth used by both the CLI and the webhook server, so they
construct dependencies identically.
"""

from __future__ import annotations

from .budget import Budget
from .clients.git_client import build_git_client
from .clients.prometheus_client import RealPrometheusClient
from .config import Config
from .llm import build_llm
from .models import AlertEvent, Investigation
from .orchestrator import investigate_async


def _build_k8s():
    """Construct the real Kubernetes client lazily (needs cluster/kubeconfig)."""
    from .clients.kubernetes_client import RealKubernetesClient

    return RealKubernetesClient()


async def handle_alert(
    incident: AlertEvent,
    config: Config,
    *,
    k8s=None,
    deliver: bool = True,
) -> Investigation:
    """Wire dependencies from ``config`` and run a full investigation.

    ``k8s`` may be injected (tests / custom readers); otherwise the real
    in-cluster/kubeconfig client is built.
    """
    k8s = k8s or _build_k8s()
    prometheus = RealPrometheusClient(config.prometheus_url) if config.prometheus_url else None
    git = build_git_client(config.git_provider, config.git_token, config.git_repo)
    llm = build_llm(config)
    budget = Budget(
        token_budget=config.token_budget,
        time_budget_seconds=config.time_budget_seconds,
    )

    investigation = await investigate_async(
        incident, k8s=k8s, llm=llm, prometheus=prometheus, git=git, budget=budget
    )

    if deliver and config.slack_webhook_url:
        from .delivery.slack import post_to_slack

        try:
            post_to_slack(config.slack_webhook_url, investigation)
        except Exception:  # noqa: BLE001 - delivery failure must not lose the result
            pass

    return investigation
