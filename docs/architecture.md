# 📐 Architecture & API Reference

SYNAPSE is built with a modular local-first architecture.

---

## 🏛️ System Architecture

```
┌───────────────────────────────┐       ┌───────────────────────────────┐
│     Chrome Extension (MV3)    │       │       Browser SPA Dashboard   │
│  (content.js, popup.js, bg)   │       │   (backend/static/index.html) │
└──────────────┬────────────────┘       └──────────────┬────────────────┘
               │                                       │
               │ HTTP POST /api/articles               │ REST API
               ▼                                       ▼
┌───────────────────────────────────────────────────────────────────────┐
│                           FastAPI Backend                             │
│                         (backend/main.py)                             │
└──────────────┬───────────────────────────────┬────────────────────────┘
               │                               │
               ▼                               ▼
┌───────────────────────────────┐       ┌───────────────────────────────┐
│        SQLite Database        │       │      Google Vertex AI         │
│  (backend/synapse_veille.db)  │       │     (gemini-2.5-flash)        │
└───────────────────────────────┘       └───────────────────────────────┘
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| `GET` | `/` | Serves static SPA dashboard (`index.html`). |
| `GET` | `/api/stats` | Returns total articles, favorites count, category count. |
| `GET` | `/api/articles` | Filter articles by category, tag, search query, favorite. |
| `POST` | `/api/articles` | Creates or updates an article entry. |
| `GET` | `/api/categories` | Returns category counts. |
| `POST` | `/api/extract` | Scrapes metadata from a given URL. |
| `POST` | `/api/ai/enrich/{id}` | Triggers live Gemini 2.5 Flash summary & tagging. |
| `POST` | `/api/ai/chat` | Global Knowledge Base RAG Chatbot. |
| `POST` | `/api/ai/article-chat` | Article Q&A chatbot with Web Search fallback. |
| `POST` | `/api/ai/newsletter` | Generates weekly Markdown digest. |
