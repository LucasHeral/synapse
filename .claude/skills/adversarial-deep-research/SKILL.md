---
name: adversarial-deep-research
description: "Adversarial deep research and opinion radar on tech entities."
version: 0.1.0
author: Hermes
metadata:
  hermes:
    tags: [Research, Sentiment, Radar, Deep-Research, Competitive-Intelligence]
---

# Adversarial Deep Research & Tech Intelligence

Conducts uncompromised, adversarial strategic intelligence and sentiment radar on tech entities (companies, AI models, frameworks, or CEOs). Discards promotional PR fluff by combining multi-axis adversarial queries, native Google Search grounding, verified source attribution, time-series snapshots, and isolated local storage. Does not pollute primary watch feeds with synthetic analyses or perform ungrounded sentiment guesswork.

## When to Use

- Analyzing market perception, sentiment, or hidden controversies on a tech company, model, or executive.
- Evaluating an entity where marketing hype obscures technical limitations, governance battles, or business model pivots.
- Tracking sentiment shifts across time with historical snapshot selectors and qualitative evolution notes.
- Generating balanced Pros and Cons with mandatory, clickable canonical source links for every single point.
- Building an Opinion Radar or competitive intelligence matrix for tech watch workflows.

## Prerequisites

- Python 3.9+ with `google-genai`, `requests`, and `google-auth` installed.
- Google Cloud Application Default Credentials configured (`gcloud auth application-default login`) with access to Vertex AI (`gemini-2.5-flash`).
- No external scraping proxies needed when using native search grounding.

## How to Run

Invoke investigation scripts through the `terminal` tool. Inspect and edit local pipeline files using `read_file`, `search_files`, and `patch`. Never push code to remote repositories without explicit user validation.

## Quick Reference

- **Dynamic Adversarial Axes**: Moat & Sovereignty, Critiques & Controversies, Business Model & Pivots, Developer Ground Truth.
- **Search Tooling**: Use native Vertex AI `types.Tool(google_search=types.GoogleSearch())` instead of scraping HTML endpoints to prevent HTTP 202 bot blocks.
- **Concurrent URL Unwrapping**: Resolve `vertexaisearch` tracking redirects to canonical target URLs in parallel using `ThreadPoolExecutor` to eliminate 15-30s sequential blocking delays.
- **Temporal Tracking**: Auto-save every snapshot with timestamps, offer a historical date selector dropdown, and compute qualitative evolution notes (no math deltas) on refresh.
- **Data Isolation**: Store reports in a dedicated `sentiment_reports` table; do NOT insert into user curation feeds (`articles`).
- **Citation Rule**: Every single Pro and Con bullet MUST include 1-2 clickable web links (`title` and `url`).
- **UI Boundary**: Never leak developer-only tooling (e.g. Swagger `/docs`) into user-facing dashboard navigation.

## Procedure

### 1. Adversarial Multi-Axis Framing
Do not execute a single generic query like `"<entity> reviews"`. Frame 4 distinct, complementary research angles:
1. **Moat & Ecosystem Forces**: Sovereign backing, key institutional investors, strategic partnerships, core architectural advantages.
2. **Adversarial Critique & Controversies**: Deliberately query `controversies critiques limitations problems complaints issues`. Limiting factors rarely appear on page 1 of generic searches.
3. **Business Model & Strategic Pivots**: Revenue sustainability, consulting/services drift vs pure frontier R&D, compute provider lock-in, governance conflicts.
4. **Developer & Community Ground Truth**: Practitioner benchmarks, Reddit, Hacker News, and community sentiment.

### 2. Native Search Grounding (Zero Scraping Blocks)
Avoid direct HTTP scraping of web search engines (such as DuckDuckGo HTML), which frequently trigger HTTP 202 bot challenges. Instead, configure the Vertex AI Gemini client with native Google Search grounding:

```python
from google.genai import types
import json, re

prompt = f"""Tu es un analyste stratégique senior de haut niveau.
Effectue une étude d'opinion et de sentiment approfondie, objective et sans concession sur : "{entity}".
Utilise l'outil de recherche Google pour trouver les dernières actualités, les débats récents, les avis de la communauté (Reddit, Hacker News, presse tech), les controverses et les points forts.

Format de réponse EXCLUSIVEMENT en JSON pur :
{{
  "entity": "{entity}",
  "sentiment_score": 70,
  "sentiment_label": "Plutôt Favorable",
  "summary": "Synthèse globale...",
  "news_and_trends": "Dernières actualités et ce qui se dit...",
  "pros": [
    {{"point": "• **Titre** : Détail...", "sources": [{{"title": "Source"}}]}}
  ],
  "cons": [
    {{"point": "• **Titre** : Détail...", "sources": [{{"title": "Source"}}]}}
  ]
}}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
)
```

### 3. Concurrent Canonical URL Unwrapping & Source Attribution
Google Vertex AI wraps search results in tracking URLs (`vertexaisearch.cloud.google.com/grounding-api-redirect/...`). LLMs frequently truncate or hallucinate characters in these long hashes, causing 404 errors when clicked. Always unwrap them concurrently to canonical URLs using `ThreadPoolExecutor`:

```python
from concurrent.futures import ThreadPoolExecutor


def unwrap_redirect_url(url: str) -> str:
    if not url or "grounding-api-redirect" not in url:
        return url
    try:
        r = requests.head(url, allow_redirects=False, timeout=1.5)
        if r.status_code in [301, 302, 303, 307, 308] and "Location" in r.headers:
            return r.headers["Location"]
    except Exception:
        pass
    return url


# Unwrap all candidate grounding chunks in parallel (<200ms total)
raw_urls = [chunk.web.uri for chunk in grounding_chunks if getattr(chunk, "web", None)]
with ThreadPoolExecutor(max_workers=5) as executor:
    canonical_urls = list(executor.map(unwrap_redirect_url, raw_urls))
```

- Bind 1-2 verified, canonical web links to each Pro and Con item.

### 4. Time-Series Snapshots & Qualitative Evolution Notes
- **Auto-Save**: Save every generated analysis automatically into `sentiment_reports` with `created_at = CURRENT_TIMESTAMP`. Drop any `UNIQUE` constraint on entity name to support historical snapshot sequences.
- **Unbiased Re-Analysis**: When the user requests an update/refresh, run the fresh web investigation *from scratch* without priming the model with the old summary, preserving objectivity.
- **Qualitative Comparison**: After the new analysis is produced, compare it against the latest prior snapshot to generate a concise, qualitative `evolution_note`:
  ```python
  prompt = f"""Compare la situation actuelle de "{entity}" avec l'analyse précédente datant du {prev_date}.
  Ancienne situation: {prev_summary}
  Nouvelle situation: {new_summary}
  Rédige une courte note d'évolution (2-3 phrases) expliquant si la situation a changé, les nouveaux événements ou les controverses apparues. Pas de calcul mathématique de delta, explique directement les faits."""
  ```
- **Timeline Navigation**: Expose a snapshot selector dropdown in the UI (`📅 YYYY-MM-DD HH:MM - Score%`) allowing users to travel back to previous analyses in 1 click.

### 5. Feed Hygiene & RAG Indexing
- Store reports in an isolated table (e.g. `sentiment_reports`). Never insert synthetic reports into the main articles feed to avoid polluting the user's manual curation.
- Inject saved reports into the RAG Chatbot context (`SELECT * FROM sentiment_reports ORDER BY updated_at DESC LIMIT 20`) so the assistant can answer cross-entity intelligence questions.

### 6. Safe Git Discipline & UI Boundaries
- Keep code iterations running on localhost (`http://localhost:8000`).
- Run `make lint`, `make format`, and `make test`.
- Do NOT push commits to remote git repositories until the user has tested and given explicit validation.
- Keep developer-only links (e.g. Swagger `/docs`) out of end-user navigation interfaces.

## Pitfalls

- **Sequential Blocking Redirect Resolution**: Calling `requests.head()` sequentially over 10-15 grounding URLs introduces 15-30s of artificial latency, making analysis appear hung. Use concurrent `ThreadPoolExecutor` workers to unwrap in <200ms.
- **Dangling Frontend Helper Calls After UI Refactors**: Removing UI elements (like a model selector dropdown) while leaving references to helper functions (e.g. `getSelectedModel()`) in API fetch payloads causes silent `ReferenceError` exceptions that leave loading spinners spinning indefinitely. Always stub or remove dangling helpers and handle fetch catch blocks with visual error states.
- **External Extraction Timeouts on Walled Gardens**: Running full-text scrapers like `trafilatura` on login-walled or rate-limited sites (e.g. LinkedIn) hangs for 10-15s per article. Guard extraction to skip protected domains and only trigger when cached content is genuinely absent.
- **Grounding Tracking Redirect 404s**: Passing `vertexaisearch` tracking links directly to the client causes 404 errors when the model corrupts the 200-char hash or when session tokens expire. Always unwrap to canonical target URLs via HTTP HEAD before returning data.
- **Prior-State Search Poisoning**: Feeding previous report summaries into a refresh search query anchors the model to stale narratives. Always run fresh grounding from scratch first, then compare old vs new.
- **DuckDuckGo HTTP 202 Captcha Challenges**: Scraping search engines directly from server scripts triggers bot challenges that return 0 sources and cause fallback outputs. Always prefer native Google Search grounding.
- **PR Bias in Generic Searches**: Standard search algorithms rank press releases first. Without explicit adversarial queries for critiques and controversies, reports become superficial cheerleading.
- **Watch Feed Pollution**: Automatically inserting opinion reports into the user's main article stream destroys curation signal; keep radar history in an isolated store.
- **Leaking Dev Tools into User UI**: Putting Swagger/OpenAPI documentation buttons into consumer interfaces confuses users. Keep developer references in development documentation and CLI tooling.
- **Premature Git Pushing**: Pushing unverified code during rapid prototyping creates noisy git commit histories. Always wait for explicit user sign-off.

## Verification

Run the test suite and verify live analysis returns valid scores, news, and canonical direct links:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ai/sentiment \
  -H "Content-Type: application/json" \
  -d '{"entity":"Mistral AI"}' | grep -E "sentiment_score|news_and_trends|sources|available_snapshots"
```
