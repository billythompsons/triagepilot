"""Generate docs/architecture.svg for Triagepilot. Run: python3 docs/make_diagram.py"""
import pathlib

W, H = 1240, 760
BG, INK = "#0e1526", "#e8eefc"
BOX, BOX2, BOX3 = "#16233f", "#1d3a5f", "#3f2d1d"
ACC, ACC2, GREEN = "#5aa2ff", "#9d7bff", "#4cc38a"
MUT = "#93a1c0"


def box(x, y, w, h, fill, stroke, title, lines=(), tsize=17, lsize=13):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>']
    s.append(f'<text x="{x + w/2}" y="{y + 30}" text-anchor="middle" fill="{INK}" font-size="{tsize}" font-weight="700" font-family="sans-serif">{title}</text>')
    yy = y + 56
    for ln in lines:
        s.append(f'<text x="{x + w/2}" y="{yy}" text-anchor="middle" fill="{MUT}" font-size="{lsize}" font-family="sans-serif">{ln}</text>')
        yy += 21
    return "\n".join(s)


def arrow(x1, y1, x2, y2, color=ACC, label="", dashed=False):
    d = f"M{x1},{y1} L{x2},{y2}"
    dash = ' stroke-dasharray="7,6"' if dashed else ""
    s = [f'<path d="{d}" stroke="{color}" stroke-width="2" fill="none"{dash} marker-end="url(#ah)"/>']
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
        s.append(f'<text x="{mx}" y="{my}" text-anchor="middle" fill="{color}" font-size="12.5" font-family="sans-serif">{label}</text>')
    return "\n".join(s)


parts = [f'<rect width="{W}" height="{H}" fill="{BG}"/>',
         '<defs><marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L8,4.5 L0,9 z" fill="#5aa2ff"/></marker></defs>',
         f'<text x="40" y="52" fill="{INK}" font-size="26" font-weight="800" font-family="sans-serif">Triagepilot — architecture</text>',
         f'<text x="40" y="78" fill="{MUT}" font-size="14" font-family="sans-serif">Strands Agents SDK · model-agnostic · dry-run safe by default</text>']

# CLI (left)
parts.append(box(40, 120, 210, 150, BOX, ACC, "CLI",
                 ["triagepilot triage", "OWNER/REPO --limit N", "--apply (opt-in writes)", "triagepilot demo"]))
# Config
parts.append(box(40, 300, 210, 150, BOX, ACC2, "config.py",
                 ["TRIAGEPILOT_PROVIDER", "ollama · openrouter · demo", "GITHUB_TOKEN (optional)", ".env.example"]))
# Agent (center)
parts.append(box(330, 180, 320, 270, BOX2, ACC, "Strands Agent",
                 ["agent.py — Agent(model, tools,", "  system_prompt)", "", "system prompt: expert OSS", "maintainer triage workflow", "", "event loop: reason → act →", "observe → report"]))
# Models (right top)
parts.append(box(730, 120, 220, 150, BOX, GREEN, "Model providers",
                 ["ollama/qwen2.5 — local, $0", "openrouter/* — via LiteLLM", "demo — scripted policy", "(offline, deterministic)"]))
# Tools (right bottom)
parts.append(box(730, 300, 220, 200, BOX, ACC, "6 GitHub tools",
                 ["fetch_open_issues", "fetch_issue (+comments)", "list_repo_labels", "search_similar_issues", "apply_labels  ⚠ gated", "post_comment  ⚠ gated"]))
# Data sources
parts.append(box(330, 510, 320, 130, BOX3, "#c98a4b", "Data",
                 ["GitHub REST API (urllib)", "fixtures/demo_issues.json", "in demo mode — no network"]))
# Output
parts.append(box(1000, 180, 200, 200, BOX, GREEN, "Output",
                 ["triage report (.md)", "table: # · category", "labels · priority · action", "per-issue draft reply", "", "dry-run note"]))
# Safety badge
parts.append(box(1000, 420, 200, 130, "#2d1d1d", "#e06c6c", "Safety gate",
                 ["writes need BOTH:", "TRIAGEPILOT_APPLY=1", "and GITHUB_TOKEN", "else: dry-run only"]))

# Arrows
parts.append(arrow(250, 195, 330, 250, label="prompt"))
parts.append(arrow(250, 375, 330, 350, label="settings", color=ACC2))
parts.append(arrow(650, 250, 730, 195, label="stream()"))
parts.append(arrow(730, 250, 650, 330, color=GREEN, label="tool calls"))
parts.append(arrow(760, 450, 560, 510, label="reads"))
parts.append(arrow(840, 450, 840, 510, label="reads"))
parts.append(arrow(560, 640, 200, 470, color="#c98a4b", label="issues / labels", dashed=True))
parts.append(arrow(650, 400, 1000, 280, color=GREEN, label="report md"))
parts.append(arrow(840, 500, 1060, 420, color="#e06c6c", label="blocked unless --apply", dashed=True))

svg = ("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"%d\" height=\"%d\" viewBox=\"0 0 %d %d\">\n%s\n</svg>"
       % (W, H, W, H, "\n".join(parts)))
out = pathlib.Path(__file__).parent / "architecture.svg"
out.write_text(svg)
print("wrote", out, len(svg), "bytes")
