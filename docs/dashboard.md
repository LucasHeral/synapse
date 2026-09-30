# 🖥️ Web Dashboard & AI Features

The SYNAPSE Web Dashboard (`http://localhost:8000`) provides a modern dark glassmorphism SPA interface for viewing, reading, synthesizing, and chatting with your curated knowledge.

---

## 📸 Dashboard Overview

![SYNAPSE Web Dashboard](assets/dashboard-overview.png)

---

## ⚡ Key Capabilities

### 1. Dual Reading Mode
Every article card includes two distinct triggers:
- **`📖 Lire`**: Opens the Reader Modal displaying the full multi-paragraph article body (`art.content`).
- **`✨ Résumé IA`**: Opens the Reader Modal in summary mode, displaying a 3-5 bullet point synthesis in French with bolded key terms. If a summary does not exist, Gemini 2.5 Flash generates it on the fly in real-time.

### 2. Interactive Article Q&A Chatbot
Located at the bottom of the Reader Modal:
- Allows asking questions specific to the article currently being read.
- **Web Search Integration**: Automatically performs live DuckDuckGo web searches when the query asks for recent facts, competitors, or external context, adding a `🌐 Recherche Web` badge to the response.
- Delivers succinct, bulleted answers.

### 3. Global Knowledge Base Chatbot
Accessible via the sidebar **`Chatbot`** tab:
- Analyzes the full corpus of saved articles in SQLite.
- Provides cited answers linking back to specific articles and authors in your watch feed.

### 4. Weekly Newsletter Digest
Accessible via the **`Newsletter Hebdo`** tab:
- Groups articles saved over the last 7 days by topic.
- Generates a structured Markdown newsletter ready for email or publication.
