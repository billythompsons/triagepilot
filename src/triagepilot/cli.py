"""CLI: triagepilot triage OWNER/REPO | triagepilot demo"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent import triage_repo
from .config import Settings


def _load_dotenv() -> None:
    env = Path.cwd() / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def cmd_triage(args: argparse.Namespace) -> int:
    _load_dotenv()
    if args.apply:
        os.environ["TRIAGEPILOT_APPLY"] = "1"
    settings = Settings.from_env()
    print(f"[triagepilot] provider={settings.provider} repo={args.repo} "
          f"limit={args.limit} apply={settings.apply_changes}")
    report = triage_repo(args.repo, args.limit, settings)
    print()
    print(report)
    if args.out:
        Path(args.out).write_text(report)
        print(f"\n[triagepilot] report written to {args.out}")
    return 0


def cmd_demo(_args: argparse.Namespace) -> int:
    """Fully offline demo: scripted model + fixture issues, no network, no cost."""
    os.environ["TRIAGEPILOT_PROVIDER"] = "demo"
    settings = Settings.from_env()
    print("[triagepilot] demo mode: scripted model + fixture issues (offline, $0)")
    report = triage_repo("triagepilot-demo/focusflow", 6, settings)
    print()
    print(report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="triagepilot",
        description="AI maintainer that triages GitHub issues (Strands Agents SDK).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("triage", help="Triage open issues in a GitHub repo.")
    p.add_argument("repo", help="Repo as OWNER/REPO, e.g. octocat/Hello-World")
    p.add_argument("--limit", type=int, default=20, help="Max issues to triage (default 20)")
    p.add_argument("--apply", action="store_true",
                   help="Actually apply labels/comments (needs GITHUB_TOKEN; default is dry-run)")
    p.add_argument("--out", help="Write the triage report markdown to this file")
    p.set_defaults(func=cmd_triage)

    d = sub.add_parser("demo", help="Run the offline demo (no network, no API keys).")
    d.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # keep CLI errors readable
        print(f"[triagepilot] error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
