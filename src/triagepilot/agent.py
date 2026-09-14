"""The Triagepilot agent: a Strands agent that triages GitHub issues."""

from __future__ import annotations

from strands import Agent

from .config import Settings, build_model
from .tools_github import (
    apply_labels,
    fetch_issue,
    fetch_open_issues,
    list_repo_labels,
    post_comment,
    search_similar_issues,
)

SYSTEM_PROMPT = """You are Triagepilot, an expert open-source maintainer triaging GitHub issues.

Workflow for each triage run:
1. Call fetch_open_issues for the repo to get the open issues.
2. Call list_repo_labels so every label you suggest actually exists on the repo.
3. For each issue, call fetch_issue to read the full body and comments.
4. For issues that look like they might already be reported, call search_similar_issues
   to check for duplicates before deciding.
5. Decide per issue: category (bug | feature | docs | question | duplicate),
   labels (only from the repo's label list), priority (high | normal | low),
   and whether it duplicates another issue.
6. Draft a short, kind maintainer reply for each issue (2-4 sentences).
7. If asked to apply changes and the tools report dry-run mode, do NOT attempt
   workarounds — report the proposed label/comment changes in your summary instead.

Finish with a markdown triage report: a table (#, title, category, labels,
priority, action) followed by one section per issue with the draft reply.
Be decisive. Prefer existing labels. Never invent label names.
"""

TOOLS = [
    fetch_open_issues,
    fetch_issue,
    list_repo_labels,
    search_similar_issues,
    apply_labels,
    post_comment,
]


def build_agent(settings: Settings) -> Agent:
    """Build the Strands triage agent for the configured provider."""
    return Agent(
        model=build_model(settings),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        name="triagepilot",
        description="GitHub issue triage agent",
    )


def result_text(result) -> str:
    """Extract plain text from a Strands AgentResult."""
    chunks: list[str] = []
    for block in result.message.get("content", []):
        if "text" in block:
            chunks.append(block["text"])
    return "\n".join(chunks)


def triage_repo(repo: str, limit: int = 20, settings: Settings | None = None) -> str:
    """Run one triage pass over a repo's open issues. Returns the report markdown."""
    settings = settings or Settings.from_env()
    agent = build_agent(settings)
    mode = "demo (scripted model + fixtures, fully offline)" if settings.demo_mode else (
        f"{settings.provider}"
    )
    prompt = (
        f"Triage the {limit} most recent open issues in {repo}. "
        f"Provider mode: {mode}. "
        + ("Do not apply any changes; dry-run only, and say so in the report."
           if not settings.apply_changes else
           "Apply the label and comment changes with the tools.")
    )
    result = agent(prompt)
    return result_text(result)
