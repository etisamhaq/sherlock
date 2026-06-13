"""In-memory fakes implementing the client protocols, plus scenario builders."""

from __future__ import annotations


class FakeKubernetesClient:
    def __init__(self, pods=None, events=None, logs="", raise_on_list=False):
        self._pods = pods or []
        self._events = events or []
        self._logs = logs
        self._raise_on_list = raise_on_list
        self.calls: list[str] = []

    def get_pod(self, namespace, name):
        self.calls.append("get_pod")
        for p in self._pods:
            if p.get("name") == name:
                return p
        return self._pods[0] if self._pods else {}

    def get_pod_events(self, namespace, name):
        self.calls.append("get_pod_events")
        return self._events

    def get_pod_logs(self, namespace, name, *, previous=True, tail=100):
        self.calls.append("get_pod_logs")
        return self._logs

    def list_workload_pods(self, namespace, workload):
        self.calls.append("list_workload_pods")
        if self._raise_on_list:
            raise RuntimeError("kube API unreachable")
        return self._pods


class FakePrometheusClient:
    def __init__(self, results=None):
        # results: dict mapping a substring of the query -> result vector
        self._results = results or {}

    def query(self, promql):
        for key, value in self._results.items():
            if key in promql:
                return value
        return []


class FakeGitClient:
    def __init__(self, commits=None, raise_error=False):
        self._commits = commits or []
        self._raise = raise_error

    def recent_commits(self, limit=10):
        if self._raise:
            raise RuntimeError("git API error")
        return self._commits[:limit]


# --- scenario builders ---------------------------------------------------

def oom_pod(name="api-7d9f8c6b5-abc12", memory_limit="256Mi", restarts=5):
    return {
        "name": name,
        "phase": "Running",
        "container_statuses": [
            {
                "name": "api",
                "ready": False,
                "restart_count": restarts,
                "waiting_reason": "CrashLoopBackOff",
                "terminated_reason": None,
                "last_terminated_reason": "OOMKilled",
                "last_exit_code": 137,
                "memory_limit": memory_limit,
            }
        ],
    }


def crashloop_pod(name="api-7d9f8c6b5-abc12", exit_code=1, restarts=7):
    return {
        "name": name,
        "phase": "Running",
        "container_statuses": [
            {
                "name": "api",
                "ready": False,
                "restart_count": restarts,
                "waiting_reason": "CrashLoopBackOff",
                "terminated_reason": None,
                "last_terminated_reason": "Error",
                "last_exit_code": exit_code,
                "memory_limit": "512Mi",
            }
        ],
    }


def pending_pod(name="api-7d9f8c6b5-abc12"):
    return {
        "name": name,
        "phase": "Pending",
        "container_statuses": [],
    }


def imagepull_pod(name="api-7d9f8c6b5-abc12"):
    return {
        "name": name,
        "phase": "Pending",
        "container_statuses": [
            {
                "name": "api",
                "ready": False,
                "restart_count": 0,
                "waiting_reason": "ImagePullBackOff",
                "terminated_reason": None,
                "last_terminated_reason": None,
                "last_exit_code": None,
                "memory_limit": "512Mi",
            }
        ],
    }


def sample_commits():
    return [
        {
            "sha": "a1b2c3d4",
            "message": "perf: lower memory limit to 256Mi",
            "author": "Dev One",
            "date": "2026-06-13T09:30:00Z",
            "url": "https://github.com/acme/api/commit/a1b2c3d4",
        },
        {
            "sha": "e5f6a7b8",
            "message": "feat: add caching layer",
            "author": "Dev Two",
            "date": "2026-06-12T14:00:00Z",
            "url": "https://github.com/acme/api/commit/e5f6a7b8",
        },
    ]
