"""Delivery: render an Investigation to text (CLI) or Slack."""

from .slack import format_text, format_slack_blocks, post_to_slack

__all__ = ["format_text", "format_slack_blocks", "post_to_slack"]
