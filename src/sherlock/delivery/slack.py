"""Render investigations for humans: plain text (CLI) and Slack Block Kit."""

from __future__ import annotations

import requests

from ..models import Investigation

_CONF_EMOJI = {"high": "🟢", "medium": "🟡", "low": "🔴"}


def format_text(inv: Investigation) -> str:
    """A compact, terminal-friendly rendering used by the CLI and stdout fallback."""
    a = inv.analysis
    lines = [
        "=" * 70,
        f"SHERLOCK · {inv.incident.workload} ({inv.incident.namespace})",
        f"Failure mode: {inv.failure_mode.value}   "
        f"Confidence: {a.overall_confidence.upper()}   "
        f"({inv.duration_ms} ms, {inv.tokens_spent} tokens)",
        "=" * 70,
        "",
        a.summary,
        "",
    ]
    if a.needs_human:
        lines.append("⚠️  NEEDS HUMAN — evidence was insufficient for a confident root cause.")
        lines.append("")
    for i, h in enumerate(a.hypotheses, 1):
        lines.append(f"[{i}] ({h.confidence.upper()}) {h.cause}")
        lines.append(f"    Why: {h.explanation}")
        lines.append(f"    Fix: {h.suggested_fix}")
        if h.evidence:
            lines.append("    Evidence:")
            for e in h.evidence[:6]:
                lines.append(f"      - {e}")
        lines.append("")
    return "\n".join(lines)


def format_slack_blocks(inv: Investigation) -> dict:
    """A Slack Block Kit payload (works with an incoming webhook)."""
    a = inv.analysis
    emoji = _CONF_EMOJI.get(a.overall_confidence, "⚪")
    header = f"{emoji} Sherlock · {inv.incident.workload} · {inv.failure_mode.value}"

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": header[:150]}},
        {"type": "section", "text": {"type": "mrkdwn", "text": a.summary[:2900] or "_no summary_"}},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Namespace:* {inv.incident.namespace}  |  "
                    f"*Confidence:* {a.overall_confidence}  |  "
                    f"*Latency:* {inv.duration_ms} ms  |  *Tokens:* {inv.tokens_spent}",
                }
            ],
        },
    ]

    if a.needs_human:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":warning: *Needs human* — evidence was insufficient for a confident root cause.",
                },
            }
        )

    for i, h in enumerate(a.hypotheses[:3], 1):
        ev = "\n".join(f"• {e}" for e in h.evidence[:5])
        text = (
            f"*[{i}] ({h.confidence.upper()}) {h.cause}*\n"
            f"*Why:* {h.explanation}\n"
            f"*Suggested fix:* {h.suggested_fix}"
        )
        if ev:
            text += f"\n*Evidence:*\n{ev}"
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text[:2900]}})

    # Feedback buttons — start the data flywheel from day one.
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "👍 Helpful"},
                 "value": f"helpful:{inv.incident.fingerprint}", "action_id": "sherlock_helpful"},
                {"type": "button", "text": {"type": "plain_text", "text": "👎 Off"},
                 "value": f"off:{inv.incident.fingerprint}", "action_id": "sherlock_off"},
            ],
        }
    )
    return {"blocks": blocks}


def post_to_slack(webhook_url: str, inv: Investigation, *, timeout: float = 10.0) -> bool:
    """Post the investigation to a Slack incoming webhook. Returns success."""
    if not webhook_url:
        return False
    resp = requests.post(webhook_url, json=format_slack_blocks(inv), timeout=timeout)
    return resp.ok
