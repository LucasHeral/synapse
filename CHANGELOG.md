# Changelog

All notable changes to the **SYNAPSE** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-30

### Added
- **Chrome Extension (Manifest V3)**:
  - Full webpage body extraction.
  - Native LinkedIn bookmark button 🔖 injected cleanly under feed posts.
  - Clean domain detection for web sources (`Lemonde.fr`, `Github.com`).
- **Dashboard Web UI**:
  - Dual reading mode: **Article Complet** (full text) vs **Résumé IA** (Vertex AI Gemini).
  - On-the-fly AI summary generation with structured key takeaways.
  - Interactive **Article Q&A Chatbot** with automatic web search integration.
  - Global Knowledge Base Chatbot for querying all saved content.
  - Weekly Newsletter & Digest Generator with 1-click Markdown export.
- **Developer Experience**:
  - `uv` package management & locking (`uv.lock`).
  - `Makefile` with clean development targets.
  - Pre-commit hooks (`ruff`, `trailing-whitespace`, `check-yaml`).
  - GitHub Actions CI workflow.
