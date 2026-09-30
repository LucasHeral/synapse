# 🧩 SYNAPSE - Chrome Extension (Manifest V3)

The **SYNAPSE Chrome Extension** allows users to capture any web article, news post, or LinkedIn update into their local SYNAPSE tech watch hub in 1 click.

---

## 🚀 Features

- **Single-Click Ingestion**: Captures page title, full body text content, author, publication date, and metadata.
- **Clean Source Extraction**: Automatically detects and formats the base domain name (`Lemonde.fr`, `Full Stack Data Lab`, `Github.com`).
- **Native LinkedIn Integration**: Injects a clean, compact bookmark button 🔖 directly under LinkedIn feed posts.
- **Strict URN Link Protection**: Prevents link hijacking by extracting LinkedIn technical URNs (`urn:li:activity:...` or `urn:li:share:...`) as true permalinks.
- **Background API Proxying**: Bypasses browser Mixed Content / CORS restrictions by relaying local HTTP requests (`http://localhost:8000`) through `background.js`.

---

## 🛠️ Installation Instructions

1. Open **Google Chrome** and navigate to `chrome://extensions`.
2. Toggle on **Developer mode** in the top right corner.
3. Click **Load unpacked** (Charger l'extension non empaquetée) and select this `chrome-extension/` directory.
4. Make sure the SYNAPSE backend server is running locally (`make dev` or `./start.sh` at `http://localhost:8000`).

---

## 📋 Manifest V3 Permissions

- `activeTab` & `scripting`: Scrapes metadata and body text from the active tab.
- `contextMenus`: Enables right-click context menu shortcuts.
- `host_permissions`: `<all_urls>`, `http://localhost:8000/*` to allow API communication with local server across all web pages.
