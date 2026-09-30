// Synapse AI Background Service Worker - Handles API proxying & context menus
const API_URL = "http://localhost:8000/api";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "add-to-synapse",
    title: "Enregistrer dans ma veille Synapse AI",
    contexts: ["page", "selection", "link"]
  });
});

// Proxy save requests from Content Script (bypasses HTTPS -> HTTP Mixed Content block)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "saveArticle") {
    fetch(`${API_URL}/articles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.data)
    })
    .then(async (res) => {
      if (res.ok) {
        const json = await res.json();
        sendResponse({ success: true, data: json });
      } else {
        let errDetail = "Erreur serveur";
        try {
          const err = await res.json();
          errDetail = err.detail || errDetail;
        } catch(e) {}
        sendResponse({ success: false, error: errDetail });
      }
    })
    .catch((err) => {
      console.error("Fetch error in background script:", err);
      sendResponse({ success: false, error: "Serveur local hors ligne ou inacessible" });
    });

    return true; // Async response
  }
});

// Context menu click handler
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "add-to-synapse") {
    const targetUrl = info.linkUrl || info.pageUrl || tab.url;
    const selectedText = info.selectionText || "";

    try {
      const extractRes = await fetch(`${API_URL}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: targetUrl })
      });

      let meta = {
        url: targetUrl,
        title: tab.title || targetUrl,
        summary: selectedText || "",
        site_name: "LinkedIn",
        category: "Tech & IA"
      };

      if (extractRes.ok) {
        meta = await extractRes.json();
        if (selectedText) meta.summary = selectedText;
      }

      const saveRes = await fetch(`${API_URL}/articles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(meta)
      });

      if (saveRes.ok) {
        console.log("Article saved successfully via context menu!");
      }
    } catch (err) {
      console.error("Failed to save via context menu:", err);
    }
  }
});
