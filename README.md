# Triagepilot ✈️

**An AI maintainer that triages your GitHub issues — built with the [Strands Agents SDK](https://strandsagents.com).**

Solo maintainers drown in untriaged issues: no labels, silent duplicates, and
questions that never get answered. Triagepilot is a Strands agent that does the
first pass for you — it fetches open issues, reads each one, checks for
duplicates, suggests labels from your repo's real label set, and drafts kind
maintainer replies. It is **dry-run safe by default**: it never writes to GitHub
unless you pass `--apply` with a token.

Built for the [Agents for Humans hackathon](https://agentsforhumans.devpost.com/).

## What it does

```
$ triagepilot triage octocat/Hello-World --limit 20

| # | Title                              | Category | Labels              | Priority | Action                  |
|---|------------------------------------|----------|---------------------|----------|-------------------------|
| #42 | Crash on startup when offline     | bug      | bug, priority:high  | high     | Label + reply           |
| #41 | App crashes when airplane mode... | duplicate| duplicate           | normal   | Close as duplicate of #42 |
| ... | ...                                | ...      | ...                 | ...      | ...                     |

## #42 — Crash on startup when offline
- **Suggested labels:** bug, priority:high
- **Draft reply:**
> Thanks for the detailed report — especially the repro steps and logcat...
```

## Quickstart (2 minutes, $0)

Triagepilot runs **fully offline** out of the box — no API keys, no network, no
cost — using a scripted demo model and fixture issues:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
triagepilot demo
```

## Real usage (still $0)

**Option A — local Ollama (default, free):**

```bash
# install from https://ollama.com, then:
ollama pull qwen2.5
cp .env.example .env   # TRIAGEPILOT_PROVIDER=ollama is the default
triagepilot triage OWNER/REPO --limit 20
```

**Option B — OpenRouter (uses your existing subscription):**

```bash
cp .env.example .env
# set: TRIAGEPILOT_PROVIDER=openrouter, OPENROUTER_API_KEY=..., OPENROUTER_MODEL=...
triagepilot triage OWNER/REPO --limit 20
```

**Applying changes** (labels + comments) requires a token and an explicit flag:

```bash
export GITHUB_TOKEN=ghp_...          # needs repo scope for private repos
triagepilot triage OWNER/REPO --apply # without --apply: dry-run report only
```

Without a token, public repos still work (60 req/hr unauthenticated).

## How it works

See [ARCHITECTURE.md](ARCHITECTURE.md) and [`docs/architecture.svg`](docs/architecture.svg).

- **Agent** (`src/triagepilot/agent.py`): a Strands `Agent` with a maintainer
  system prompt and six tools. Model-agnostic: LiteLLM for Ollama/OpenRouter.
- **Tools** (`src/triagepilot/tools_github.py`): `fetch_open_issues`,
  `fetch_issue`, `list_repo_labels`, `search_similar_issues`, `apply_labels`,
  `post_comment` — GitHub REST via stdlib, dry-run gated.
- **Providers** (`src/triagepilot/config.py`): `TRIAGEPILOT_PROVIDER` picks
  `ollama` / `openrouter` / `demo`.
- **Demo model** (`src/triagepilot/demo_model.py`): a deterministic `strands`
  `Model` implementation that drives the real agent tool loop against bundled
  fixtures — reproducible demos with zero cost.

## Tests

```bash
PYTHONPATH=src python scripts/smoke_test.py   # full agent loop, demo mode
```

## License

MIT — see [LICENSE](LICENSE).
