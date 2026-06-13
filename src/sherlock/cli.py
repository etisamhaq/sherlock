"""Sherlock command-line interface.

    sherlock investigate --namespace prod --workload api   # manual investigation
    sherlock serve --port 8080                              # run the webhook server
    sherlock version
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from . import __version__
from .config import Config
from .delivery.slack import format_text
from .models import AlertEvent, Severity
from .runtime import handle_alert


def _cmd_investigate(args: argparse.Namespace) -> int:
    config = Config.from_env()
    incident = AlertEvent(
        source="cli",
        title=args.title or f"Manual investigation of {args.workload}",
        namespace=args.namespace,
        workload=args.workload,
        severity=Severity(args.severity),
    )
    inv = asyncio.run(handle_alert(incident, config, deliver=not args.no_deliver))
    if args.json:
        print(inv.model_dump_json(indent=2))
    else:
        print(format_text(inv))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .intake.webhook import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _cmd_version(_args: argparse.Namespace) -> int:
    print(f"sherlock {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sherlock", description="AI SRE that root-causes Kubernetes incidents.")
    sub = p.add_subparsers(dest="command", required=True)

    inv = sub.add_parser("investigate", help="Run a one-off investigation against a workload.")
    inv.add_argument("--namespace", "-n", required=True)
    inv.add_argument("--workload", "-w", required=True, help="Deployment/workload name.")
    inv.add_argument("--title", default="", help="Optional alert title/context.")
    inv.add_argument("--severity", default="warning", choices=[s.value for s in Severity])
    inv.add_argument("--json", action="store_true", help="Emit the full Investigation as JSON.")
    inv.add_argument("--no-deliver", action="store_true", help="Don't post to Slack.")
    inv.set_defaults(func=_cmd_investigate)

    srv = sub.add_parser("serve", help="Run the webhook server.")
    srv.add_argument("--host", default="0.0.0.0")
    srv.add_argument("--port", type=int, default=8080)
    srv.set_defaults(func=_cmd_serve)

    ver = sub.add_parser("version", help="Print version.")
    ver.set_defaults(func=_cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
