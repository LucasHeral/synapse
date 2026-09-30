// Synapse AI Content Script - LinkedIn Integration & Clean Extractor

const API_URL = "http://localhost:8000/api";

console.log("%c 🚀 Synapse AI Active on " + window.location.href, "background: #6366f1; color: #ffffff; font-weight: bold; font-size: 14px; padding: 4px 8px; border-radius: 4px;");

// Initialize LinkedIn Injection
if (window.location.hostname.includes("linkedin.com")) {
  initLinkedInInjector();
}

function initLinkedInInjector() {
  injectCustomStyles();

  scanAndInjectButtons();
  setInterval(scanAndInjectButtons, 800);

  const observer = new MutationObserver(() => {
    scanAndInjectButtons();
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function injectCustomStyles() {
  if (document.getElementById("synapse-ai-styles")) return;
  const style = document.createElement("style");
  style.id = "synapse-ai-styles";
  style.textContent = `
    /* Synapse AI Bookmark Badge - Far Right Positioned */
    .synapse-ai-action-btn-wrapper {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      margin-left: auto !important;
      padding: 0 4px !important;
      flex-shrink: 0 !important;
    }
    .synapse-ai-native-btn {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      background: rgba(99, 102, 241, 0.1) !important;
      color: #8b5cf6 !important;
      border: 1px solid rgba(139, 92, 246, 0.35) !important;
      border-radius: 8px !important;
      width: 34px !important;
      height: 34px !important;
      padding: 0 !important;
      cursor: pointer !important;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
      box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15) !important;
      box-sizing: border-box !important;
    }
    .synapse-ai-native-btn:hover {
      background: rgba(139, 92, 246, 0.22) !important;
      border-color: #8b5cf6 !important;
      color: #7c3aed !important;
      transform: translateY(-1px) !important;
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.35) !important;
    }
    .synapse-ai-native-btn.saved {
      background: rgba(16, 185, 129, 0.2) !important;
      color: #10b981 !important;
      border-color: #10b981 !important;
    }
    .synapse-icon-svg {
      width: 17px;
      height: 17px;
      fill: currentColor;
      flex-shrink: 0;
    }

    /* Dark mode support */
    .theme--dark .synapse-ai-native-btn {
      background: rgba(168, 85, 247, 0.15) !important;
      color: #c084fc !important;
      border-color: rgba(168, 85, 247, 0.4) !important;
    }
    .theme--dark .synapse-ai-native-btn:hover {
      background: rgba(168, 85, 247, 0.3) !important;
      color: #e9d5ff !important;
    }
  `;
  document.head.appendChild(style);
}

function findActionBarRow(btn) {
  let current = btn.parentElement;
  for (let i = 0; i < 5 && current && current !== document.body; i++) {
    const buttons = current.querySelectorAll('button');
    if (buttons.length >= 2) {
      let hasLikeOrComment = false;
      buttons.forEach(b => {
        const txt = (b.innerText || b.ariaLabel || "").toLowerCase();
        if (txt.includes("j’aime") || txt.includes("j'aime") || txt.includes("like") || txt.includes("commenter") || txt.includes("comment") || txt.includes("republier") || txt.includes("envoyer")) {
          hasLikeOrComment = true;
        }
      });
      if (hasLikeOrComment) {
        return current;
      }
    }
    current = current.parentElement;
  }
  return btn.closest('.feed-shared-social-actions, .social-details-social-actions') || btn.parentElement;
}

function scanAndInjectButtons() {
  const actionBars = new Set();

  document.querySelectorAll('.feed-shared-social-actions, .social-details-social-actions, .feed-shared-social-action-bar').forEach(el => actionBars.add(el));

  document.querySelectorAll('button').forEach(btn => {
    const text = (btn.innerText || btn.ariaLabel || "").toLowerCase().trim();
    if (text.includes("j’aime") || text.includes("j'aime") || text.includes("like") || text.includes("commenter") || text.includes("comment")) {
      const row = findActionBarRow(btn);
      if (row) actionBars.add(row);
    }
  });

  actionBars.forEach((bar) => {
    // Strict Exclusion: Ignore all comment boxes, replies, and comment trees
    if (bar.closest('.comments-comment-item') || 
        bar.closest('.comments-comments-list') || 
        bar.closest('.comments-comment-box') || 
        bar.closest('.feed-shared-comment') ||
        bar.closest('.comments-comment-entity') ||
        bar.closest('[data-testid*="comment"]') ||
        bar.closest('div[class*="comment"]') ||
        bar.closest('section[class*="comment"]')) {
      return;
    }

    if (bar.querySelector('.synapse-ai-action-btn-wrapper')) return;

    const wrapper = document.createElement("div");
    wrapper.className = "synapse-ai-action-btn-wrapper";

    // Premium Bookmark / Tech Curation SVG Icon
    const defaultIconHTML = `
      <svg class="synapse-icon-svg" viewBox="0 0 24 24">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 14l-3.5-2.25L5 17V5h14v12l-3.5-2.25L12 17z"/>
      </svg>
    `;

    wrapper.innerHTML = `
      <button type="button" class="synapse-ai-native-btn" title="Enregistrer ce post dans Synapse AI">
        ${defaultIconHTML}
      </button>
    `;

    const btn = wrapper.querySelector("button");

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const postCard = findPostCard(bar);
      const data = extractLinkedInPostData(postCard);

      btn.innerHTML = `<span style="font-size:12px;">⏳</span>`;

      chrome.runtime.sendMessage({ action: "saveArticle", data }, (response) => {
        if (response && response.success) {
          btn.classList.add("saved");
          btn.innerHTML = `
            <svg class="synapse-icon-svg" viewBox="0 0 24 24" style="fill: #10b981;">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          `;
          setTimeout(() => {
            btn.classList.remove("saved");
            btn.innerHTML = defaultIconHTML;
          }, 3000);
        } else {
          console.error("Save failed:", response ? response.error : "No response");
          btn.innerHTML = `<span style="font-size:12px;">❌</span>`;
          setTimeout(() => { 
            btn.innerHTML = defaultIconHTML;
          }, 2000);
        }
      });
    });

    bar.appendChild(wrapper);
  });
}

function findPostCard(startEl) {
  if (!startEl) return document.body;

  let current = startEl;
  for (let i = 0; i < 15 && current && current !== document.body; i++) {
    if (current.matches && (
      current.matches('div.feed-shared-update-v2') ||
      current.matches('div[data-id*="urn:li:"]') ||
      current.matches('div[data-urn*="urn:li:"]') ||
      current.matches('article')
    )) {
      return current;
    }
    if (current.querySelector('[data-testid*="expandable-text"]') ||
        current.querySelector('p[componentkey]') ||
        current.querySelector('.update-components-text') || 
        current.querySelector('.feed-shared-update-v2__description') ||
        current.querySelector('.update-components-actor') ||
        current.querySelector('.feed-shared-actor')) {
      return current;
    }
    current = current.parentElement;
  }
  return startEl.parentElement || startEl;
}

function extractAuthorName(postContainer) {
  if (!postContainer) return "";

  // Strategy 1: Control menu button aria-label (e.g. "Ouvrir le menu de contrôle pour le post de Corine De Bilbao")
  const menuBtn = postContainer.querySelector('button[aria-label*="post de"], button[aria-label*="post by"]');
  if (menuBtn) {
    const aria = menuBtn.getAttribute('aria-label') || "";
    const match = aria.match(/post (?:de|by)\s+([^,.]+)/i);
    if (match && match[1]) {
      const clean = match[1].trim();
      if (clean) return clean;
    }
  }

  // Strategy 2: Specific author elements
  const authorSpan = postContainer.querySelector('p[style*="--_9a86c5a9"] span') ||
                     postContainer.querySelector('.update-components-actor__title span[dir="ltr"]') ||
                     postContainer.querySelector('.update-components-actor__title span') ||
                     postContainer.querySelector('.update-components-actor__title') ||
                       postContainer.querySelector('.update-components-actor__name') ||
                     postContainer.querySelector('.feed-shared-actor__name') ||
                     postContainer.querySelector('a[data-field="actor_card_search"] span');

  if (authorSpan && authorSpan.innerText) {
    const text = authorSpan.innerText.trim().split('\n')[0].trim();
    if (text && !text.toLowerCase().includes('abonnés')) return text;
  }

  // Strategy 3: Actor header block fallback
  const anyAuthorEl = postContainer.querySelector('.update-components-actor, .feed-shared-actor');
  if (anyAuthorEl && anyAuthorEl.innerText) {
    const lines = anyAuthorEl.innerText.split('\n').map(l => l.trim()).filter(Boolean);
    if (lines.length > 0 && !lines[0].toLowerCase().includes('abonnés')) {
      return lines[0];
    }
  }

  return "";
}

// Technical URN extractor (Strictly technical identity of post, no arbitrary external links)
function extractRealPostUrl(postContainer) {
  if (!postContainer) return null;

  // 1. Search LinkedIn technical URN attributes directly on the post
  const candidates = [
    postContainer.getAttribute("data-urn"),
    postContainer.getAttribute("data-activity-urn"),
    postContainer.getAttribute("data-id"),
    postContainer.querySelector("[data-urn]")?.getAttribute("data-urn"),
    postContainer.querySelector("[data-activity-urn]")?.getAttribute("data-activity-urn"),
    postContainer.querySelector("[data-id*='urn:li:']")?.getAttribute("data-id"),
  ].filter(Boolean);

  for (const value of candidates) {
    const match = value.match(/urn:li:(?:activity|share):\d+/);
    if (match) {
      return `https://www.linkedin.com/feed/update/${match[0]}/`;
    }
  }

  // 2. Direct LinkedIn permalink href
  const permalink = postContainer.querySelector(
    'a[href*="/feed/update/urn:li:activity:"], ' +
    'a[href*="/feed/update/urn:li:share:"]'
  );

  if (permalink?.href) {
    const match = permalink.href.match(/urn:li:(?:activity|share):\d+/);
    if (match) {
      return `https://www.linkedin.com/feed/update/${match[0]}/`;
    }
  }

  // 3. Embedded-post iframe URL
  const iframe = postContainer.querySelector(
    'iframe[src*="/embed/feed/update/urn:li:"]'
  );

  if (iframe?.src) {
    const match = iframe.src.match(/urn:li:(?:activity|share):\d+/);
    if (match) {
      return `https://www.linkedin.com/feed/update/${match[0]}/`;
    }
  }

  // IMPORTANT: Do NOT fallback to arbitrary lnkd.in, safety/go, profile, or external links
  return null;
}

function extractLinkedInPostData(postContainer) {
  let url = null;
  let author = "";
  let summary = "";
  let title = "";

  if (postContainer) {
    // 1. Extract Author Name via multi-strategy locator
    author = extractAuthorName(postContainer);

    // 2. Extract Full Post Text Content
    const textEl = postContainer.querySelector('[data-testid="expandable-text-box"]') ||
                   postContainer.querySelector('[data-testid*="expandable-text"]') ||
                   postContainer.querySelector('p[componentkey] span') ||
                   postContainer.querySelector('p[componentkey]') ||
                   postContainer.querySelector('.update-components-text') ||
                   postContainer.querySelector('.feed-shared-update-v2__description') ||
                   postContainer.querySelector('.feed-shared-inline-show-more-text') ||
                   postContainer.querySelector('div[dir="ltr"]') ||
                   postContainer.querySelector('span.break-words');

    if (textEl) {
      summary = textEl.innerText.trim();
    }

    // 3. Extract Real URL via strict Technical URN Priority Chain
    url = extractRealPostUrl(postContainer);

    // 4. Title generation
    if (author && summary) {
      const excerpt = summary.slice(0, 65).replace(/\n/g, ' ');
      title = `Post de ${author} : "${excerpt}..."`;
    } else if (author) {
      title = `Post de ${author}`;
    } else if (summary) {
      title = summary.slice(0, 70).replace(/\n/g, ' ');
    } else {
      title = `Post LinkedIn (${new Date().toLocaleDateString('fr-FR')})`;
    }
  } else {
    title = document.title || "Post LinkedIn";
  }

  return {
    url,
    title,
    summary,
    content: summary,
    author,
    site_name: "LinkedIn",
    category: "LinkedIn",
    notes: author ? `Auteur : ${author}` : "Ajouté depuis le fil LinkedIn"
  };
}

// Global Message Listener for Extension Popup ("extractPageData")
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "extractPageData") {
    let siteName = "Web";
    try {
      siteName = window.location.hostname.replace(/^www\./, "");
    } catch (e) {}

    const ogSite = document.querySelector('meta[property="og:site_name"]')?.content;
    if (ogSite && ogSite.trim()) {
      siteName = ogSite.trim();
    }

    // Format domain nicely (e.g. lemonde.fr -> Lemonde.fr, github.com -> Github.com)
    if (siteName.includes(".")) {
      const parts = siteName.split(".");
      if (parts[0]) {
        siteName = parts[0].charAt(0).toUpperCase() + parts[0].slice(1) + "." + parts.slice(1).join(".");
      }
    } else {
      siteName = siteName.charAt(0).toUpperCase() + siteName.slice(1);
    }

    let title = document.title || "";
    const ogTitle = document.querySelector('meta[property="og:title"]')?.content ||
                    document.querySelector('meta[name="twitter:title"]')?.content;
    if (ogTitle) title = ogTitle.trim();

    let summary = "";
    const selection = window.getSelection().toString().trim();
    const ogDesc = document.querySelector('meta[property="og:description"]')?.content ||
                   document.querySelector('meta[name="description"]')?.content;
    if (selection) {
      summary = selection;
    } else if (ogDesc) {
      summary = ogDesc.trim();
    }

    // Extract Full Page Article Text Content
    let fullContent = "";
    const targetEl = document.querySelector('article') || 
                     document.querySelector('main') || 
                     document.querySelector('[role="main"]') || 
                     document.body;

    if (targetEl) {
      const clone = targetEl.cloneNode(true);
      clone.querySelectorAll('script, style, nav, footer, header, aside, iframe, noscript, svg, button').forEach(el => el.remove());
      fullContent = (clone.innerText || clone.textContent || "").trim();
      fullContent = fullContent.replace(/\n{3,}/g, '\n\n');
    }

    if (!summary && fullContent) {
      summary = fullContent.slice(0, 250).replace(/\n/g, ' ') + "...";
    }

    sendResponse({
      url: window.location.href,
      title: title,
      summary: summary,
      content: fullContent,
      site_name: siteName,
      image_url: document.querySelector('meta[property="og:image"]')?.content || ""
    });
  }
  return true;
});
