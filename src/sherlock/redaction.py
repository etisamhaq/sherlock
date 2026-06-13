"""Secret/PII redaction.

Untrusted log and event text passes through the LLM. We redact obvious secrets
*before* anything leaves the cluster. This is a defense-in-depth measure, not a
guarantee — it runs on every investigator's evidence text.
"""

from __future__ import annotations

import re

# (label, compiled pattern). Order matters: more specific patterns first.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |)PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("BEARER_TOKEN", re.compile(r"(?i)\b(bearer|token|authorization)\b['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{12,}")),
    ("PASSWORD_KV", re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key)\b['\"]?\s*[:=]\s*['\"]?[^\s'\"]{4,}")),
    ("CONN_STRING_PW", re.compile(r"://[^:@/\s]+:([^@/\s]+)@")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

_REDACTED = "«REDACTED:{}»"


def redact(text: str) -> str:
    """Return ``text`` with recognized secrets/PII replaced by a labeled marker."""
    if not text:
        return text
    out = text
    for label, pattern in _PATTERNS:
        if label == "CONN_STRING_PW":
            # Only redact the password group inside a connection string.
            out = pattern.sub(lambda m: m.group(0).replace(m.group(1), _REDACTED.format(label)), out)
        else:
            out = pattern.sub(_REDACTED.format(label), out)
    return out


def redact_lines(lines: list[str]) -> list[str]:
    return [redact(line) for line in lines]
