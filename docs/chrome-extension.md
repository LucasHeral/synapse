# 🧩 Chrome Extension (Manifest V3)

The SYNAPSE Chrome Extension allows users to capture any web article, news post, or LinkedIn update into their local SYNAPSE hub in 1 click.

---

## 📸 Extension Screenshot

![Chrome Extension Popup](assets/chrome-extension-popup.png)

---

## 🛠️ Features & Architecture

1. **Auto Domain Detection**: Automatically extracts and formats the clean source domain (e.g. `Spotify Engineering`, `Full Stack Data Lab`, `Github.com`).
2. **Full Page Body Extraction**: Scrapes the complete multi-paragraph text body from `<article>` or `<main>` elements, stripping navigation, scripts, and footers.
3. **LinkedIn Native Integration**: Injects a compact bookmark button 🔖 cleanly into LinkedIn feed action bars.
4. **Technical URN Protection**: Extracts LinkedIn technical URNs (`urn:li:activity:...` or `urn:li:share:...`) as true permalinks to prevent body link hijacking.
5. **Background Proxying**: Bypasses browser Mixed Content / CORS restrictions by relaying local HTTP requests (`http://localhost:8000`) through `background.js`.

---

## 📥 Installation

1. Open `chrome://extensions` in Google Chrome.
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the `chrome-extension/` directory.
