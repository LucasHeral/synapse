const API_URL = "http://localhost:8000/api";

let extractedPageContent = "";

document.addEventListener("DOMContentLoaded", async () => {
  // Query active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab || !tab.url) {
    showToast("Impossible d'accéder à l'onglet actif", "error");
    return;
  }

  // Pre-fill basic URL & title
  document.getElementById("url").value = tab.url;
  document.getElementById("title").value = tab.title || "";

  // Extract clean domain name from active tab URL
  let detectedDomain = "";
  try {
    const parsedUrl = new URL(tab.url);
    const domain = parsedUrl.hostname.replace(/^www\./, "");
    if (tab.url.includes("linkedin.com")) {
      detectedDomain = "LinkedIn";
    } else if (domain.includes(".")) {
      const parts = domain.split(".");
      detectedDomain = parts[0].charAt(0).toUpperCase() + parts[0].slice(1) + "." + parts.slice(1).join(".");
    } else {
      detectedDomain = domain.charAt(0).toUpperCase() + domain.slice(1);
    }
  } catch (e) {
    detectedDomain = "Web";
  }

  // Set initial siteName
  document.getElementById("siteName").value = detectedDomain;

  // Request content script data
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { action: "extractPageData" });
    if (response) {
      if (response.title) document.getElementById("title").value = response.title;
      if (response.summary) document.getElementById("summary").value = response.summary;
      if (response.site_name && !tab.url.includes("linkedin.com")) {
        document.getElementById("siteName").value = response.site_name;
      }
      if (response.image_url) document.getElementById("imageUrl").value = response.image_url;
      if (response.content) extractedPageContent = response.content;

      // Smart category suggestion
      const autoCat = detectCategory(response.url || tab.url, response.title || tab.title, response.summary || "", response.site_name || detectedDomain);
      document.getElementById("category").value = autoCat;
    } else {
      const autoCat = detectCategory(tab.url, tab.title || "", "", detectedDomain);
      document.getElementById("category").value = autoCat;
    }
  } catch (err) {
    // Content script fallback to backend extract endpoint
    fetchExtractFromBackend(tab.url, detectedDomain);
  }

  // Check backend connectivity
  checkBackendHealth();

  // Form submission handler
  document.getElementById("saveForm").addEventListener("submit", handleSave);
});

async function checkBackendHealth() {
  const badge = document.getElementById("statusBadge");
  try {
    const res = await fetch(`${API_URL}/stats`, { method: "GET" });
    if (res.ok) {
      badge.textContent = "Connecté";
      badge.style.color = "#10b981";
      badge.style.background = "rgba(16, 185, 129, 0.15)";
    } else {
      throw new Error();
    }
  } catch (e) {
    badge.textContent = "Hors ligne";
    badge.style.color = "#f87171";
    badge.style.background = "rgba(239, 68, 68, 0.15)";
  }
}

async function fetchExtractFromBackend(url, fallbackDomain) {
  try {
    const res = await fetch(`${API_URL}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.title) document.getElementById("title").value = data.title;
      if (data.summary) document.getElementById("summary").value = data.summary;
      if (data.site_name && !url.includes("linkedin.com")) {
        document.getElementById("siteName").value = data.site_name;
      } else {
        document.getElementById("siteName").value = fallbackDomain;
      }
      
      const autoCat = detectCategory(url, data.title || "", data.summary || "", data.site_name || fallbackDomain);
      document.getElementById("category").value = autoCat;
    }
  } catch (e) {}
}

function detectCategory(url, title, summary, siteName) {
  // Category MUST be 'LinkedIn' ONLY if the URL is from linkedin.com
  if (url && url.toLowerCase().includes("linkedin.com")) {
    return "LinkedIn";
  }

  const text = `${title} ${summary} ${url} ${siteName}`.toLowerCase();
  
  if (text.match(/\b(ai|ia|llm|gpt|claude|gemini|machine learning|deep learning|prompt|neural|vllm|sql engine|model)\b/)) {
    return "Tech & IA";
  }
  if (text.match(/\b(code|dev|python|javascript|react|github|api|backend|frontend|rust|go)\b/)) {
    return "Dev & Tech";
  }
  if (text.match(/\b(business|startup|saas|marketing|finance|growth|strategy)\b/)) {
    return "Business & SaaS";
  }
  if (text.match(/\b(design|ui|ux|figma|css)\b/)) {
    return "Design & UX";
  }
  if (text.match(/\b(security|cyber|privacy|hack)\b/)) {
    return "Sécurité";
  }

  return "Tech & IA";
}

async function handleSave(e) {
  e.preventDefault();

  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.innerHTML = `<span>Enregistrement en cours...</span>`;

  const payload = {
    url: document.getElementById("url").value,
    title: document.getElementById("title").value.trim(),
    category: document.getElementById("category").value,
    site_name: document.getElementById("siteName").value.trim(),
    summary: document.getElementById("summary").value.trim(),
    content: extractedPageContent || "",
    notes: document.getElementById("notes").value.trim(),
    image_url: document.getElementById("imageUrl").value,
    is_favorite: document.getElementById("isFavorite").checked
  };

  try {
    const res = await fetch(`${API_URL}/articles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast("✓ Ajouté à votre veille avec succès !", "success");
      setTimeout(() => {
        window.close();
      }, 1200);
    } else {
      const errData = await res.json();
      showToast(`Erreur: ${errData.detail || "Sauvegarde impossible"}`, "error");
      btn.disabled = false;
      btn.innerHTML = `<span>Enregistrer dans ma veille</span>`;
    }
  } catch (err) {
    showToast("Impossible de contacter le serveur local (l'app Synapse est-elle lancée ?)", "error");
    btn.disabled = false;
    btn.innerHTML = `<span>Enregistrer dans ma veille</span>`;
  }
}

function showToast(message, type) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.style.display = "block";
}