# AGENTS.md — Developer & AI Agent Instructions for SYNAPSE

Welcome to **SYNAPSE**! This document provides concise, high-signal context and operational rules for AI coding agents (Hermes, Claude Code, Codex, Cursor) and human developers working in this repository.

---

## 🚀 Repository Mission & Architecture

**SYNAPSE** is a local-first Tech Watch & Knowledge Hub that pairs a **Chrome Extension (Manifest V3)** with a **FastAPI + SQLite** backend and a modern **Glassmorphism Web Dashboard**.

### Core Stack
- **Package Manager**: `uv` (Astral) with `pyproject.toml` and `uv.lock`.
- **Backend API**: Python 3.9+ / FastAPI, `uvicorn`, `pydantic`.
- **Database**: SQLite (`backend/synapse_veille.db`) managed via `backend/database.py`.
- **LLM / AI Engine**: Google Vertex AI (`gemini-2.5-flash`) via `google.genai` SDK and Application Default Credentials (ADC).
- **Web Extraction**: `trafilatura` and `BeautifulSoup4` for full-text body extraction.
- **Frontend UI**: Single-page application (`backend/static/index.html`) using Tailwind CSS CDN and FontAwesome.
- **Chrome Extension**: Manifest V3 extension in `chrome-extension/` with content script injection, popup form, and background service worker API proxying.

---

## 🛠️ Operational Commands (`Makefile`)

Always use the `Makefile` or `uv` to execute tasks:

```bash
# Install venv and sync dependencies
make install

# Run local development server (http://127.0.0.1:8000)
make dev

# Run linters (ruff check)
make lint

# Format code (ruff format)
make format

# Run unit tests (pytest)
make test

# Install pre-commit hooks
make precommit
```

---

## 📐 Key Architecture & Design Rules

### 1. Database & Nullable URLs
- The `url` column in SQLite is `NULLABLE`. Never require a non-null URL for posts (e.g. LinkedIn posts without a direct permalink are stored with `url = NULL`).
- In the frontend dashboard, always validate `hasValidUrl = art.url && art.url !== 'null' && String(art.url).startsWith('http')` before rendering anchor tags.

### 2. Chrome Extension (Manifest V3) Rules
- **Host Permissions**: `manifest.json` must specify `"<all_urls>"` and `"http://localhost:8000/*"` to communicate across arbitrary HTTPS sites.
- **Single Message Listener**: `content.js` MUST contain exactly **one** `chrome.runtime.onMessage.addListener` block to prevent message intercept collisions.
- **LinkedIn Permalinks**: LinkedIn post permalinks MUST come exclusively from technical URNs (`urn:li:activity:\d+` or `urn:li:share:\d+`). Never fall back to arbitrary `lnkd.in` or profile links in post bodies.

### 3. AI & Vertex AI Gemini Integration
- Primary model is configured via `GEMINI_MODEL` (default: `gemini-2.5-flash`).
- All AI responses must be formatted as **ultra-succinct French bullet points** (`• `) with bold key terms (`**concept**`).
- The article Q&A endpoint (`/api/ai/article-chat`) supports dynamic web search context via DuckDuckGo fallback when the user requests recent/external information.

### 4. Code Quality & Security
- All Python code MUST pass `ruff check .` and `ruff format .`.
- Do NOT hardcode API keys, tokens, or credentials in any file or summary.
- Refer to `CONCEPTS.md` for project domain vocabulary definitions.

---

## 📂 Key File Map

| Path | Purpose |
| ---- | ------- |
| `backend/main.py` | FastAPI application, endpoints, lifespan event, CORS setup. |
| `backend/ai_service.py` | Vertex AI Gemini calls, summary generation, RAG, and article Q&A. |
| `backend/database.py` | SQLite connection, table schema creation, and migrations. |
| `backend/models.py` | Pydantic request & response models. |
| `backend/static/index.html` | Dashboard Web SPA UI (Reader modal, AI synthesis, Chatbot). |
| `chrome-extension/content.js` | Content script for page scraping & LinkedIn button injection. |
| `chrome-extension/popup.js` | Extension popup form, domain extraction, category auto-fill. |
| `chrome-extension/manifest.json` | Extension Manifest V3 configuration & permissions. |
| `solutions/` | Engineering learnings capitalised via `ce-compound`. |
| `CONCEPTS.md` | Domain vocabulary and concept definitions. |
| `tests/test_api.py` | `pytest` test suite for API endpoints. |
