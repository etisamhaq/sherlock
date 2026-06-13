# Contributing to Sherlock

Thanks for helping build the open-source AI SRE. Sherlock is deliberately narrow
right now (four Kubernetes failure modes, done well). The fastest way to help:

## Good first contributions

- **A new investigator** — e.g. a Loki/Elasticsearch log backend, a trace
  (OpenTelemetry/Jaeger) investigator, or a Redis/Kafka/Postgres signal source.
  Implement `Investigator` (`src/sherlock/investigators/base.py`), inject a
  read-only client, return a `Finding` with cited `Evidence`.
- **A new failure mode** — add detection to `classify.py` and a heuristic branch
  to `llm/fake.py`, with tests.
- **A new intake source** — add a parser to `intake/parsers.py` (pure function,
  easy to test) and an endpoint to `intake/webhook.py`.

## Ground rules

1. **Every finding must cite evidence.** No naked assertions. Never let the agent
   bluff a confident root cause it can't support — set `needs_human=True` instead.
2. **Investigators must be resilient.** A failing source returns `Finding.error`,
   never an exception that sinks the whole investigation.
3. **Redact untrusted text** (`redaction.redact`) before it reaches the LLM.
4. **Stay read-only.** No write/delete calls to the cluster. Auto-remediation is a
   future, separately-gated capability — not something an investigator does.
5. **Tests run offline.** Use the fakes in `tests/fakes.py`; never require a real
   cluster, Prometheus, Git, or API key in CI.

## Dev loop

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python examples/demo.py
```

## Style

Match the surrounding code. Type hints, small focused modules, docstrings that
explain *why*. Keep dependencies lean.
