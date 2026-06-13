# Sherlock 🔍 — the open-source AI SRE for Kubernetes

**When a Kubernetes workload breaks, Sherlock tells you _why_ — and which deploy did it — in Slack, before you finish reading the page.**

k8sgpt explains the pod. **Sherlock explains the incident** — across pod state, events, logs, Prometheus metrics, and the recent deploy that caused it — and posts a ranked, *evidence-cited* root cause with a confidence score.

```
======================================================================
SHERLOCK · api (prod)
Failure mode: OOMKilled   Confidence: HIGH   (1 ms, 0 tokens)
======================================================================

The workload is being OOMKilled (out-of-memory). A recent deploy
(a1b2c3d4 perf: lower memory limit to 256Mi) is the most likely trigger.

[1] (HIGH) Container was OOMKilled — memory usage exceeded its limit, and a
    recent deploy (a1b2c3d4 perf: lower memory limit to 256Mi) likely changed it
    Why: The pod's last termination reason is OOMKilled. The memory limit is
         256Mi. A deploy happened shortly before the incident — the top signal.
    Fix: Revert a1b2c3d4 or raise the memory limit; then profile real usage.
    Evidence:
      - [k8s-status]  container 'api' reason=OOMKilled, restarts=5, exit_code=137
      - [k8s-events]  BackOff: Back-off restarting failed container api
      - [prometheus]  peak working-set memory ≈ 268 MB
      - [git]         a1b2c3d4 perf: lower memory limit to 256Mi (Dev One)
```

---

## Why Sherlock

- **"What changed" correlation** — links the incident to the deploy/PR that caused it. This is the highest-signal root-cause feature, and the thing other tools skip.
- **Evidence + confidence on every claim** — no naked assertions, no confident hallucinations. When the evidence is weak, Sherlock says *needs human*.
- **Observability-agnostic** — works across Kubernetes, Prometheus, and your Git provider. Not locked to one vendor's data.
- **10-minute install, Slack-native** — `helm install`, connect Slack + Prometheus, and your next alert gets investigated.
- **Read-only & bring-your-own-LLM** — runs in your cluster with read-only RBAC and your own LLM key (Groq or Claude). Your data isn't used to train anything.
- **Runs offline** — a deterministic engine gives a useful answer with no API key at all (great for trials and CI).

## What it investigates (v0)

The four highest-frequency Kubernetes failures, done well:

| Failure | What Sherlock does |
|---|---|
| **CrashLoopBackOff** | exit code + crash logs + correlated deploy |
| **OOMKilled** | memory limit vs. usage + the change that moved it |
| **Failed deploy / bad rollout** | image-pull/config errors + "what changed" |
| **Pending / unschedulable** | scheduling events, resource pressure, taints/PVCs |

(Kafka, Redis, DB, DNS, cert expiry, and **gated auto-remediation** are on the roadmap.)

---

## Architecture

```
            ┌──────────── Your Kubernetes cluster ─────────────┐
 Alert ────►│  Sherlock pod (read-only RBAC, outbound-only)    │
(Alertmgr / │   ┌──────────────────────────────────────────┐  │
 PagerDuty) │   │ Orchestrator (intake→investigate→classify  │  │
            │   │            →budget→synthesize)             │  │
            │   │   ├─ Kubernetes investigator (events/logs) │  │
            │   │   ├─ Metrics investigator (Prometheus)     │  │
            │   │   └─ Change investigator (GitHub/GitLab)   │  │
            │   │            ▼                               │  │
            │   │   Root-cause synthesis (Claude, cited)     │  │
            │   └──────────────┬───────────────────────────┘  │
            └──────────────────┼───────────────────────────────┘
                               ▼                ▼
                          Slack (result)   your LLM key
```

The three investigators run **in parallel**. Synthesis is the only LLM step and is bounded by a hard **token + time budget** (protects cost on alert storms). Untrusted log/event text is **redacted** before it reaches the LLM.

---

## Quick start

### Try it offline in 30 seconds (no cluster, no key)

```bash
git clone https://github.com/etisamhaq/sherlock && cd sherlock
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python examples/demo.py        # runs a full investigation on a synthetic OOM incident
```

### Run a one-off investigation against your cluster

```bash
export GROQ_API_KEY=gsk_...                   # or ANTHROPIC_API_KEY=sk-ant-... ; or SHERLOCK_LLM_PROVIDER=fake to stay offline
export SHERLOCK_PROMETHEUS_URL=http://prometheus.monitoring:9090
export SHERLOCK_GIT_PROVIDER=github SHERLOCK_GIT_TOKEN=ghp_... SHERLOCK_GIT_REPO=acme/api
sherlock investigate -n prod -w api --title "api OOMKilled"
```

### Deploy to your cluster (Helm)

```bash
kubectl create secret generic sherlock-secrets \
  --from-literal=GROQ_API_KEY=gsk_... \
  --from-literal=SHERLOCK_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

helm install sherlock deploy/helm/sherlock \
  --set config.prometheusUrl=http://prometheus-server.monitoring:80 \
  --set config.gitProvider=github --set config.gitRepo=acme/api
```

Then point Alertmanager at it:

```yaml
# alertmanager.yaml
receivers:
  - name: sherlock
    webhook_configs:
      - url: http://sherlock-sherlock.default.svc:8080/webhook/alertmanager
```

---

## Configuration

All via environment variables — see [`.env.example`](.env.example). Highlights:

| Variable | Purpose |
|---|---|
| `SHERLOCK_LLM_PROVIDER` | `auto` (default), `groq`, `anthropic`, or `fake`. `auto` = Groq → Anthropic → offline engine |
| `GROQ_API_KEY` | Groq Cloud key (primary). Get one at https://console.groq.com |
| `SHERLOCK_GROQ_MODEL` | Default `llama-3.3-70b-versatile` |
| `ANTHROPIC_API_KEY` | Claude key (fallback) |
| `SHERLOCK_LLM_MODEL` | Anthropic model, default `claude-opus-4-8` |
| `SHERLOCK_PROMETHEUS_URL` | Prometheus HTTP API base URL |
| `SHERLOCK_GIT_PROVIDER` / `_TOKEN` / `_REPO` | "what changed" correlation |
| `SHERLOCK_SLACK_WEBHOOK_URL` | Where to post results |
| `SHERLOCK_TOKEN_BUDGET` / `_TIME_BUDGET_SECONDS` | Per-investigation guardrails |

## Security posture

- **Read-only RBAC** (`get`/`list`/`watch` only) — see [`deploy/helm/sherlock/templates/rbac.yaml`](deploy/helm/sherlock/templates/rbac.yaml).
- **Outbound-only**, non-root, read-only root filesystem, all capabilities dropped.
- **Secret/PII redaction** on all evidence text before it reaches the LLM.
- **Bring-your-own-LLM**; no customer data trains shared models.

## Development

```bash
pip install -e ".[dev]"
pytest -q                 # 57 tests, fully offline
python examples/demo.py
```

## Roadmap

- v1: more log backends (Loki/Elastic), trace analysis, auto-create Jira/Linear/GitHub issues, postmortem drafts.
- v2: **gated auto-remediation** (rollback/restart/scale with approval + auto-revert), incident knowledge graph, predictive risk on deploys.
- Enterprise: self-hosted/BYO-LLM, SSO/RBAC, audit logs, SOC2/HIPAA.

## License

Apache-2.0. Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
