---
name: ab-worktree-testing
description: "A/B test code and UI redesigns across dual live ports."
version: 0.2.0
author: Hermes
metadata:
  hermes:
    tags: [Git, Worktree, Testing, UI-Review, Fullstack, Playwright]
---

# Multi-Port A/B Worktree Testing

Conduct live, side-by-side comparisons of major redesigns, migrations, or design variants across multiple ports (e.g. 8000, 8001, 8002) using isolated git worktrees. Eliminates guess-work by allowing optical inspection of competing variants running simultaneously against identical data.

## When to Use

- "test une version en mode X sur un autre port pour comparer"
- Major UI/UX redesigns where side-by-side comparison is requested.
- Comparing multiple design systems (e.g. Linear Dark vs. Apple HIG vs. Baseline).
- Breaking API or backend migrations requiring parity validation.

## Prerequisites

- Git repository with at least one commit.
- Available local ports (8000, 8001, 8002).
- `playwright-cli` (optional for headless automated screenshots): `npm install -g @playwright/cli@latest`.

## How to Run

Execute the procedure through the `terminal` tool. For visual inspection, combine `terminal` (`playwright-cli screenshot`) with `vision_analyze`.

## Quick Reference

```bash
# 1. Spawn isolated worktree in Hermes workspace (NEVER in ~/Documents/)
mkdir -p ~/.hermes/worktrees
git worktree add ~/.hermes/worktrees/<repo>-<variant> <base-or-branch> --detach

# 2. Replicate runtime state (copy, do not symlink SQLite databases)
cp backend/synapse_veille.db ~/.hermes/worktrees/<repo>-<variant>/backend/synapse_veille.db
[ -f backend/.env ] && cp backend/.env ~/.hermes/worktrees/<repo>-<variant>/backend/.env

# 3. Disambiguate browser tabs during review
# Temporarily patch <title> to '[V1 - Baseline] App' / '[V2 - Variant] App'

# 4. Launch daemon on alternate port
cd ~/.hermes/worktrees/<repo>-<variant>/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8001

# 5. Visual QA via Playwright CLI
playwright-cli goto http://localhost:8001 && playwright-cli screenshot

# 6. Clean Teardown after user decision
lsof -ti :8001 | xargs kill -9 2>/dev/null || true
git worktree remove --force ~/.hermes/worktrees/<repo>-<variant>
git worktree prune
```

## Procedure

### 1. Worktree Location Enforcement (Safety Rule)
**NEVER** create worktrees in `~/Documents/` or inside the user's primary project tree.
Always anchor temporary worktrees in `~/.hermes/worktrees/<repo>-<variant>`. Changes are merged or copied to the primary repository in `~/Documents/<repo>` ONLY after the user explicitly selects and validates the winning variant.

### 2. Spawn Isolated Worktrees
- **Baseline Worktree (Port 8001)**:
  ```bash
  git worktree add ~/.hermes/worktrees/<repo>-baseline <base-commit-hash> --detach
  ```
- **Variant B / C Worktree (Port 8002)**:
  ```bash
  git worktree add -b theme-<name> ~/.hermes/worktrees/<repo>-<variant> HEAD
  ```

### 3. Replicate Local Runtime State
Copy required environment secrets and SQLite databases:
```bash
cp <main-repo>/backend/synapse_veille.db ~/.hermes/worktrees/<repo>-<variant>/backend/synapse_veille.db
[ -f <main-repo>/backend/.env ] && cp <main-repo>/backend/.env ~/.hermes/worktrees/<repo>-<variant>/backend/.env
```
*Note: Always copy rather than symlink SQLite files to avoid SQLite database locking contention during concurrent queries.*

### 4. Disambiguate Browser Tab Titles
To prevent confusion when the user opens multiple tabs side-by-side, prepend clear version tags in `<title>`:
- Port 8001: `<title>[V1 - Baseline] AppName</title>`
- Port 8000: `<title>[V2 - VariantA] AppName</title>`
- Port 8002: `<title>[V3 - VariantB] AppName</title>`

**MANDATORY REVERT RULE**: Before creating a final git commit or push, ALWAYS revert the `<title>` back to the clean canonical production string (e.g. `<title>AppName</title>`).

### 5. Launch Daemons on Dedicated Ports
Launch each server process from its own app subdirectory:
```bash
cd ~/.hermes/worktrees/<repo>-baseline/backend
/path/to/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001
```
Run as background process (`terminal` with `background=true`).

### 6. Automated Visual Inspection with Playwright & Vision
Verify UI rendering, typography, and card alignment before handing off to the user:
```bash
playwright-cli goto http://localhost:8000 && playwright-cli screenshot
playwright-cli goto http://localhost:8002 && playwright-cli screenshot
```
Call `vision_analyze` on the resulting screenshot path to check:
- Equal column heights and baseline alignments (`line-clamp-2` on titles).
- Contrast ratios and WCAG readability.
- Sanity of tags, badges, and action buttons.

### 7. Deliver Side-by-Side Review Links
Present the URLs clearly in markdown table format:
| Port | Tab Title | Aesthetic / Direction |
| :--- | :--- | :--- |
| `8001` | `[V1 - Baseline]` | Original state before redesign |
| `8000` | `[V2 - Variant A]` | Primary redesign (e.g. Cosmic Navy) |
| `8002` | `[V3 - Variant B]` | Alternative redesign (e.g. Apple HIG) |

### 8. Clean Teardown
Once the user validates their preferred direction:
1. Kill background daemons on alternate ports:
   ```bash
   lsof -ti :8001,8002 | xargs kill -9 2>/dev/null || true
   ```
2. Remove temporary worktrees:
   ```bash
   git worktree remove --force ~/.hermes/worktrees/<repo>-baseline
   git worktree remove --force ~/.hermes/worktrees/<repo>-<variant>
   git worktree prune
   ```
3. Apply the winning changes into the main project tree in `~/Documents/<repo>` and revert `<title>` to clean production text.

## Pitfalls

- **Creating worktrees in Documents**: Violates user workspace hygiene. Always use `~/.hermes/worktrees/`.
- **Database lock contention**: Never symlink SQLite databases across two running uvicorn instances. Use `cp` to give each instance its own database connection.
- **ModuleNotFoundError**: In Python projects where modules use top-level relative imports (`from ai_service import ...`), running uvicorn from repo root fails. Always set working directory to `backend/` or use `--app-dir backend`.
- **Forgetting to revert titles**: Temporary tags like `[V2 - Cosmic Navy]` must NEVER be committed to Git. Revert to canonical title before `git commit`.
- **Pre-commit hooks modifying files**: Linters and formatting hooks (like `trailing-whitespace` or `ruff-format`) may alter files on the first commit attempt, returning exit code 1. Check `git status`, re-stage the touched files with `git add`, and re-commit immediately.
- **Never push without explicit validation**: All worktree experimentation must remain local until the user explicitly approves.

## Verification

Check that all target ports respond with identical HTTP 200 health status:
```bash
curl -s http://127.0.0.1:8000/api/stats && curl -s http://127.0.0.1:8001/api/stats && curl -s http://127.0.0.1:8002/api/stats
```
