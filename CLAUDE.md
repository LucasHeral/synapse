# CLAUDE.md — SYNAPSE Intelligence & Veille Hub

> Reference guide for Claude Code CLI and GitHub Actions automation on **SYNAPSE**.

## Overview & Architecture

**SYNAPSE** is an open-source, local-first tech-watch & competitive intelligence platform.
- **Backend**: FastAPI (Python >=3.10) with local SQLite (`synapse_veille.db`), `uv` package manager.
- **Frontend**: High-craft single page application (`backend/static/index.html`) using Tailwind CSS, `marked.js`, and hardware-inspired design tokens.
- **Extension**: Chrome Extension (Manifest V3) in `chrome-extension/` with automatic page extraction, proxy background messaging, and LinkedIn URN post handling.
- **AI Core**: Google Vertex AI Gemini (`google-genai` SDK, `gemini-2.5-flash`), with Google Search Grounding for live web exploration and adversarial deep research.

---

## Commands & Development Workflow

All primary actions are automated via `make`:

```bash
make sync       # Synchronize dependencies with uv
make dev        # Run backend server on http://localhost:8000 with auto-reload
make test       # Run pytest test suite (backend/tests)
make lint       # Run ruff check on python files
make format     # Auto-format python files with ruff
make precommit  # Install/update pre-commit hooks
```

*Note: Running `make lint`, `make format`, and `make test` before submitting code is strictly enforced.*

---

## GitHub Actions & Automation Configuration

To enable automated Claude Code GitHub Actions (`claude.yml`, `claude-review.yml`, `let-claude-cook.yml`, `let-claude-scope.yml`), you **must configure the following secrets** in your GitHub repository:

### Required GitHub Secrets

| Secret Name | Description | Example / Typical Value |
| :--- | :--- | :--- |
| `LITELLM_BASE_URL` | Base URL of your LiteLLM Gateway or Anthropic Proxy | `https://llmgateway.artechfact.fr` (or custom endpoint) |
| `LITELLM_API_KEY` | API Key for the LiteLLM gateway / Anthropic endpoint | `sk-...` |

### How to Configure Secrets on GitHub:
1. Go to your GitHub repository: `https://github.com/LucasHeral/synapse`
2. Navigate to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Click on **New repository secret**.
4. Add `LITELLM_BASE_URL` with your gateway URL.
5. Add `LITELLM_API_KEY` with your API token.

---

## Project Skills & Design Standards

Claude Code has access to the curated project skills embedded in `.claude/skills/`:

| Skill | Path | When to Use |
| :--- | :--- | :--- |
| **`web-design-guidelines`** | `.claude/skills/web-design-guidelines` | Vercel standards for accessibility (WCAG), focus rings, semantic HTML, and typography conventions. |
| **`taste-skill`** & **`soft-skill`** | `.claude/skills/taste-skill`, `.claude/skills/soft-skill` | Anti-slop frontend engineering, Double-Bezel hardware card architecture, haptic feedback (`active:scale-[0.98]`). |
| **`awesome-design-md`** | `.claude/skills/awesome-design-md` | 73 reference brand design token files (Linear, Raycast, Vercel, Stripe). See root `DESIGN.md`. |
| **`adversarial-deep-research`** | `.claude/skills/adversarial-deep-research` | Contradictory opinion radar, dynamic query formulation, and canonical URL extraction. |
| **`ab-worktree-testing`** | `.claude/skills/ab-worktree-testing` | Multi-port A/B testing via isolated git worktrees in `~/.hermes/worktrees/` (never in `~/Documents/`). |
| **`test-driven-development`** | `.claude/skills/test-driven-development` | Enforces RED-GREEN-REFACTOR for core engine changes. |
| **`systematic-debugging`** | `.claude/skills/systematic-debugging` | 4-phase root cause diagnosis loop before applying patches. |

### Design Rules
- Follow **`DESIGN.md`** for color tokens, spacing, and elevation.
- Never introduce pitch-black void (#000000) or generic purple/cyan slop gradients.
- Ban all em-dashes (`—`) in user-facing UI labels; use colons (`:`) or standard hyphens (`-`).
- Replace browser native `alert()` with the in-app `showToast()` component.
- Strictly maintain uniform card alignment with `line-clamp-2` for titles and `line-clamp-3` for excerpts.

---

## Coding Conventions

- **Language**: Python 3.10+ with type hints everywhere.
- **SQL**: SQLite with parameterized queries (`?`), foreign keys enabled.
- **Error Handling**: Graceful fallback, exponential backoff on Vertex 429 rate limits, and clear toast notifications on the UI.
