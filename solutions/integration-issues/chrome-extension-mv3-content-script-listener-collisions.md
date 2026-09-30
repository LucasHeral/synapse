---
title: Chrome Extension MV3 Content Script Message Listener Collisions & Domain Overrides
date: 2026-09-30
category: integration-issues
module: chrome-extension
problem_type: integration_issue
component: frontend
symptoms:
  - Extension popup displays Source as LinkedIn and Category as LinkedIn on non-LinkedIn web pages
  - Failure to extract full page body text and metadata on external domains
  - Uncaught SyntaxError in web dashboard breaking article card rendering
root_cause: logic_bug
resolution_type: code_fix
severity: medium
tags: [chrome-extension, manifest-v3, content-script, listener-collision, domain-extraction]
---

# Chrome Extension MV3 Content Script Message Listener Collisions & Domain Overrides

## Problem
On non-LinkedIn web pages (such as `https://fsdatalab.github.io`), opening the Chrome extension popup erroneously displayed `Source: LinkedIn` and `Category: LinkedIn`, while failing to extract page metadata and full article text. In addition, an inline JavaScript string escaping bug in the web dashboard broke card rendering whenever an article title contained single quotes.

## Symptoms
- Extension popup defaulted `site_name` and `category` to "LinkedIn" on external sites.
- Full webpage article text was not sent to the local FastAPI backend.
- Web dashboard at `http://localhost:8000` failed to render article cards due to a frontend template string `SyntaxError`.

## What Didn't Work
- Adding open-graph fallback logic in `popup.js` alone failed because an earlier `chrome.runtime.onMessage.addListener` in `content.js` intercepted the popup's message first and returned a hardcoded `{ site_name: "LinkedIn" }` payload.
- Restricted `host_permissions` in `manifest.json` (`https://*.linkedin.com/*`) blocked content script execution on arbitrary web pages.

## Solution
1. **Consolidated Message Listener**: Removed the stale duplicate listener in `content.js` and consolidated `extractPageData` into a single, clean message listener that extracts `og:site_name`, cleans `window.location.hostname`, and scrapes full body text from `<article>` or `<main>` elements.
2. **Wildcard Host Permissions**: Updated `manifest.json` `host_permissions` to include `"<all_urls>"`, `"http://*/*"`, and `"https://*/*"`.
3. **Strict Domain Detection**: Updated `popup.js` to default `site_name` from the active tab's hostname and restrict the `LinkedIn` category strictly to `linkedin.com` URLs.
4. **Safe Event Handlers**: Replaced inline string-formatted event parameters (`onclick="openNotesModal(id, 'title', ...)"`) with numeric ID handlers (`onclick="openNotesModal(id)"`) in `index.html`.

## Why This Works
- Chrome extensions execute content script listeners in registered order; multiple `onMessage` listeners handling the same `action` cause the first listener's `sendResponse` to win. Consolidating into a single listener guarantees predictable extraction.
- Manifest V3 requires explicit host permissions (`<all_urls>`) to inject content scripts and send extension messages across arbitrary domains.
- Passing numeric IDs instead of unescaped strings in `onclick` handlers eliminates HTML template string escaping bugs caused by quotes or special characters in user titles.

## Prevention
- **Single Listener Rule**: Maintain exactly one `chrome.runtime.onMessage.addListener` block in `content.js`.
- **Wildcard Permissions**: Always include `<all_urls>` in `host_permissions` for general web curation extensions.
- **ID-Based Event Delegation**: Pass primitive record IDs to inline HTML event handlers rather than interpolating raw text strings.

## Related Issues
- `manifest.json` permissions update v1.2
- `backend/static/index.html` card rendering bugfix
