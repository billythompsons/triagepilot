"""Scripted demo model: a deterministic triage policy implementing the Strands Model API.

This lets the full agent loop (Strands event loop + real GitHub tools) run
end-to-end with zero network and zero cost, using the bundled fixtures.
Swap TRIAGEPILOT_PROVIDER to ollama/openrouter for real LLM reasoning.
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncGenerator

from strands.models.model import Model

STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "is", "it", "for",
    "with", "when", "this", "that", "i", "my", "we", "you", "are", "be",
    "as", "at", "by", "from", "was", "were", "has", "have", "had", "not",
    "but", "if", "so", "do", "does", "did", "can", "could", "should", "would",
    "there", "their", "they", "them", "he", "she", "his", "her", "its", "our",
    "all", "any", "each", "how", "what", "which", "who", "will", "just",
    "than", "then", "also", "into", "over", "such", "only", "new", "app",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z]{4,}", text.lower())
    out = set()
    for w in words:
        if w in STOP_WORDS:
            continue
        # light stemming so crash/crashes, close/closes match
        if w.endswith("es") and len(w) > 5:
            w = w[:-2]
        elif w.endswith("s") and len(w) > 4 and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


class ScriptedTriageModel(Model):
    """Deterministic stand-in for an LLM: drives the triage tool workflow."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {"model_id": "triagepilot-demo-scripted"}

    # -- Model ABC ---------------------------------------------------------
    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    async def structured_output(
        self, output_model: type, prompt: Any, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"output": None}

    # -- helpers -----------------------------------------------------------
    def _text_events(self, text: str):
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        for i in range(0, len(text), 400):
            yield {"contentBlockDelta": {"delta": {"text": text[i : i + 400]}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}

    def _tool_events(self, tool_id: str, name: str, args: dict):
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {"toolUse": {"name": name, "toolUseId": tool_id}}}}
        yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}

    def _history(self, messages: list) -> tuple[str, list[dict], dict[str, list[str]], set[int], int]:
        """Return (repo, issues, tool results by tool name, fetched issue numbers, limit)."""
        repo = "triagepilot-demo/focusflow"
        limit = 6
        issues: list[dict] = []
        for m in messages or []:
            for b in m.get("content", []):
                if "text" in b and m.get("role") == "user":
                    found = re.search(r"[\w.-]+/[\w.-]+", b["text"])
                    if found:
                        repo = found.group(0)
                    lm = re.search(r"(\d+)\s+(most recent\s+)?open issues", b["text"])
                    if lm:
                        limit = max(1, int(lm.group(1)))
        # Map results: walk assistant toolUse ids in order, then user toolResults in order.
        tool_ids: list[tuple[str, str]] = []  # (id, name)
        res_blocks: list[str] = []
        for m in messages or []:
            for b in m.get("content", []):
                if "toolUse" in b:
                    tool_ids.append((b["toolUse"]["toolUseId"], b["toolUse"]["name"]))
                if "toolResult" in b:
                    tr = b["toolResult"]
                    txt = ""
                    for c in tr.get("content", []):
                        txt += c.get("text", "") if isinstance(c, dict) else str(c.get("text", ""))
                    res_blocks.append(txt)
        by_name: dict[str, list[str]] = {}
        for (tid, name), txt in zip(tool_ids, res_blocks):
            by_name.setdefault(name, []).append(txt)
        if "fetch_open_issues" in by_name:
            try:
                issues = json.loads(by_name["fetch_open_issues"][0])
            except Exception:
                issues = []
        fetched = set()
        if "fetch_issue" in by_name:
            for raw in by_name["fetch_issue"]:
                try:
                    fetched.add(json.loads(raw)["number"])
                except Exception:
                    pass
        return repo, issues, by_name, fetched, limit

    # -- main --------------------------------------------------------------
    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        repo, issues, by_name, fetched, limit = self._history(messages)
        n_calls = sum(len(v) for v in by_name.values())

        if "fetch_open_issues" not in by_name:
            events = self._tool_events(f"call-{n_calls}", "fetch_open_issues",
                                       {"repo": repo, "limit": limit})
        elif "list_repo_labels" not in by_name:
            events = self._tool_events(f"call-{n_calls}", "list_repo_labels", {"repo": repo})
        else:
            remaining = [i["number"] for i in issues if i["number"] not in fetched]
            if remaining:
                events = self._tool_events(
                    f"call-{n_calls}", "fetch_issue",
                    {"repo": repo, "number": remaining[0]})
            else:
                details = {}
                for raw in by_name.get("fetch_issue", []):
                    try:
                        d = json.loads(raw)
                        details[d["number"]] = d
                    except Exception:
                        continue
                labels = []
                try:
                    labels = json.loads(by_name["list_repo_labels"][0])
                except Exception:
                    pass
                report = triage_report(repo, issues, details, labels)
                events = self._text_events(report)

        for e in events:
            yield e


# ---------------------------------------------------------------------------
# Deterministic triage policy (the "reasoning" the demo model stands in for)
# ---------------------------------------------------------------------------

def classify(issue: dict, detail: dict) -> dict:
    text = f"{issue['title']} {detail.get('body', '')}".lower()
    if any(k in text for k in ("crash", "force-close", "force close", "exception",
                               "nullpointer", "drains battery", "battery")):
        category, label = "bug", "bug"
    elif any(k in text for k in ("typo", "docs", "documentation", "readme")):
        category, label = "docs", "documentation"
    elif text.startswith("how ") or "how do i" in text or "is there a way" in text:
        category, label = "question", "question"
    elif any(k in text for k in ("add ", "feature", "request", "support", "schedule")):
        category, label = "feature", "enhancement"
    else:
        category, label = "chore", "enhancement"

    labels = [label]
    priority = "normal"
    if category == "bug" and any(k in text for k in ("startup", "crash on", "force-close")):
        labels.append("priority:high")
        priority = "high"
    if category == "docs":
        labels.append("good first issue")
    return {"category": category, "labels": labels, "priority": priority}


def find_duplicate(issue: dict, detail: dict, older: list[dict]) -> int | None:
    mine = _keywords(f"{issue['title']} {detail.get('body', '')}")
    for other in older:  # older = lower issue numbers first
        theirs = _keywords(f"{other['title']} {other.get('body', '')}")
        if len(mine & theirs) >= 3:
            return other["number"]
    return None


REPLIES = {
    "bug": ("Thanks for the detailed report — especially the repro steps and logcat, "
            "that narrows it down a lot. I've labeled this as a {labels} issue with "
            "{priority} priority. A maintainer will dig into {area} next."),
    "feature": ("Thanks for the suggestion! This fits the roadmap. I've labeled it "
                "as an enhancement — we'll scope it and update this thread."),
    "docs": ("Good catch, thanks! Labeled as documentation and marked good first "
             "issue — a PR would be very welcome."),
    "question": ("Good question! {answer} I'm converting this to a docs task so the "
                 "answer is easier to find next time."),
    "duplicate": ("Thanks for reporting! This looks like a duplicate of #{dup} — "
                  "let's continue the discussion there so everything stays in one "
                  "place. Closing this as a duplicate."),
}


def triage_report(repo: str, issues: list[dict], details: dict, repo_labels: list[str]) -> str:
    lines = [f"# Triage report: {repo}", "",
             f"Triaged {len(issues)} open issues. Dry-run mode — no labels or comments were changed.",
             "", "| # | Title | Category | Labels | Priority | Action |",
             "|---|-------|----------|--------|----------|--------|"]
    sections = []
    older: list[dict] = []
    for issue in sorted(issues, key=lambda i: i["number"]):
        n = issue["number"]
        detail = details.get(n, {"body": issue.get("body", "")})
        older_details = [dict(details.get(o["number"], {"body": o.get("body", "")}),
                              title=o["title"]) for o in older]
        dup = find_duplicate(issue, detail, older_details)
        verdict = classify(issue, detail)
        if dup:
            verdict = {"category": "duplicate", "labels": ["duplicate"],
                       "priority": "normal", "duplicate_of": dup}
            action = f"Close as duplicate of #{dup}"
            reply = REPLIES["duplicate"].format(dup=dup)
        else:
            action = "Label + reply"
            area = "the crash" if verdict["category"] == "bug" else "this"
            answer = ""
            if verdict["category"] == "question":
                answer = "Export is under Settings > Backup > Export."
            reply = REPLIES[verdict["category"]].format(
                labels="/".join(verdict["labels"]), priority=verdict["priority"],
                area=area, answer=answer)
        # keep suggested labels to ones that exist on the repo
        suggested = [l for l in verdict["labels"] if l in repo_labels] or verdict["labels"]
        lines.append(f"| #{n} | {issue['title']} | {verdict['category']} | "
                     f"{', '.join(suggested)} | {verdict['priority']} | {action} |")
        sections.append(
            f"## #{n} — {issue['title']}\n"
            f"- **Category:** {verdict['category']} · **Priority:** {verdict['priority']}\n"
            f"- **Suggested labels:** {', '.join(suggested)}\n"
            f"- **Action:** {action}\n"
            f"- **Draft reply:**\n\n> {reply}\n")
        older.append(issue)

    return "\n".join(lines) + "\n\n" + "\n".join(sections)
