"""GitHub tools for the triage agent.

All tools work in two modes:
  - live:  GitHub REST API via stdlib urllib (GITHUB_TOKEN optional for public repos).
  - demo:  TRIAGEPILOT_PROVIDER=demo -> reads bundled fixtures, no network.

Write operations (apply_labels, post_comment) are dry-run safe: they only
describe what they *would* do unless TRIAGEPILOT_APPLY=1 and GITHUB_TOKEN is set.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from strands import tool

API = "https://api.github.com"
_FIXTURES = Path(__file__).parent / "fixtures" / "demo_issues.json"


def _demo_mode() -> bool:
    return os.environ.get("TRIAGEPILOT_PROVIDER", "ollama").strip().lower() == "demo"


def _can_write() -> bool:
    return os.environ.get("TRIAGEPILOT_APPLY", "0") == "1" and bool(os.environ.get("GITHUB_TOKEN"))


def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "triagepilot/0.1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(path: str, params: dict | None = None) -> object:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _load_fixtures() -> dict:
    return json.loads(_FIXTURES.read_text())


def _slim(issue: dict) -> dict:
    return {
        "number": issue["number"],
        "title": issue["title"],
        "author": issue["user"]["login"],
        "labels": [l["name"] for l in issue.get("labels", [])],
        "comments": issue.get("comments", 0),
        "created_at": issue.get("created_at"),
        "body": (issue.get("body") or "")[:1200],
    }


@tool
def fetch_open_issues(repo: str, limit: int = 20) -> str:
    """Fetch open issues for a GitHub repo (e.g. 'owner/repo'). Pull requests are excluded.

    Returns a JSON list of {number, title, author, labels, comments, created_at, body}.
    """
    if _demo_mode():
        data = _load_fixtures()
        issues = [i for i in data["issues"] if i.get("state") == "open"][: max(1, limit)]
        return json.dumps([_slim(i) for i in issues])
    raw = _get(f"/repos/{repo}/issues", {"state": "open", "per_page": max(1, min(limit, 100))})
    issues = [i for i in raw if "pull_request" not in i]
    return json.dumps([_slim(i) for i in issues])


@tool
def fetch_issue(repo: str, number: int) -> str:
    """Fetch one issue with its full body and all comments.

    Returns JSON {number, title, body, labels, comments: [{author, body}]}.
    """
    if _demo_mode():
        data = _load_fixtures()
        issue = next(i for i in data["issues"] if i["number"] == number)
        comments = [c for c in data.get("comments", []) if c["issue"] == number]
        return json.dumps(
            {
                "number": issue["number"],
                "title": issue["title"],
                "body": issue.get("body") or "",
                "labels": [l["name"] for l in issue.get("labels", [])],
                "comments": [{"author": c["author"], "body": c["body"]} for c in comments],
            }
        )
    issue = _get(f"/repos/{repo}/issues/{number}")
    comments = _get(f"/repos/{repo}/issues/{number}/comments")
    return json.dumps(
        {
            "number": issue["number"],
            "title": issue["title"],
            "body": issue.get("body") or "",
            "labels": [l["name"] for l in issue.get("labels", [])],
            "comments": [
                {"author": c["user"]["login"], "body": (c.get("body") or "")[:800]}
                for c in comments
            ],
        }
    )


@tool
def list_repo_labels(repo: str) -> str:
    """List the labels configured on a repo so suggested labels actually exist."""
    if _demo_mode():
        return json.dumps(_load_fixtures()["labels"])
    labels = _get(f"/repos/{repo}/labels", {"per_page": 100})
    return json.dumps([l["name"] for l in labels])


@tool
def search_similar_issues(repo: str, query: str, limit: int = 5) -> str:
    """Search a repo's issues for possible duplicates of the given query text."""
    if _demo_mode():
        data = _load_fixtures()
        q = query.lower()
        words = {w.strip(".,!?()\"'") for w in q.split() if len(w) > 3}
        scored = []
        for i in data["issues"]:
            text = f"{i['title']} {i.get('body') or ''}".lower()
            overlap = {w for w in words if w in text}
            if overlap:
                scored.append((len(overlap), i["number"], i["title"], sorted(overlap)[:6]))
        scored.sort(reverse=True)
        return json.dumps(
            [
                {"number": n, "title": t, "shared_keywords": kw}
                for _, n, t, kw in scored[: max(1, limit)]
            ]
        )
    res = _get("/search/issues", {"q": f"repo:{repo} {query} type:issue", "per_page": max(1, limit)})
    return json.dumps(
        [{"number": i["number"], "title": i["title"]} for i in res.get("items", [])]
    )


@tool
def apply_labels(repo: str, number: int, labels: list) -> str:
    """Set labels on an issue. DRY-RUN SAFE: only describes the change unless
    TRIAGEPILOT_APPLY=1 and GITHUB_TOKEN are both set."""
    labels = list(labels)
    if not _can_write():
        return (
            f"[dry-run] Would set labels {labels} on {repo}#{number}. "
            "No changes made (set TRIAGEPILOT_APPLY=1 with GITHUB_TOKEN to apply)."
        )
    req = urllib.request.Request(
        f"{API}/repos/{repo}/issues/{number}",
        data=json.dumps({"labels": labels}).encode(),
        headers={**_headers(), "Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        updated = json.loads(resp.read().decode())
    return f"Set labels {[l['name'] for l in updated.get('labels', [])]} on {repo}#{number}."


@tool
def post_comment(repo: str, number: int, body: str) -> str:
    """Post a comment on an issue. DRY-RUN SAFE: only previews the comment unless
    TRIAGEPILOT_APPLY=1 and GITHUB_TOKEN are both set."""
    if not _can_write():
        preview = body[:300] + ("..." if len(body) > 300 else "")
        return (
            f"[dry-run] Would comment on {repo}#{number}:\n---\n{preview}\n---\n"
            "No changes made (set TRIAGEPILOT_APPLY=1 with GITHUB_TOKEN to apply)."
        )
    req = urllib.request.Request(
        f"{API}/repos/{repo}/issues/{number}/comments",
        data=json.dumps({"body": body}).encode(),
        headers={**_headers(), "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        posted = json.loads(resp.read().decode())
    return f"Posted comment {posted.get('id')} on {repo}#{number}."
