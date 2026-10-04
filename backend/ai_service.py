import io
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import google.auth
import requests
import trafilatura
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_vertex_client = None


def get_vertex_client():
    global _vertex_client
    if _vertex_client is not None:
        return _vertex_client

    try:
        credentials, default_project = google.auth.default()
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or default_project
        _vertex_client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        return _vertex_client
    except Exception as e:
        print("Error initializing Vertex AI Client:", e)
        return None


def generate_with_gemini(client, prompt: str, requested_model: Optional[str] = None):
    """Generates content using requested model with 429 retry backoff and valid fallback models."""
    import time

    models_to_try = [m for m in [requested_model, GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.5-pro"] if m]

    seen = set()
    unique_models = []
    for m in models_to_try:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)

    last_error = None
    for model_name in unique_models:
        for attempt in range(2):
            try:
                res = client.models.generate_content(model=model_name, contents=prompt)
                return res.text.strip(), model_name
            except Exception as e:
                last_error = e
                err_str = str(e)
                if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt == 0:
                    time.sleep(1.5)
                    continue
                print(f"Model {model_name} failed (attempt {attempt + 1}):", err_str[:120])
                break

    raise last_error or Exception("All Gemini models failed.")


def is_youtube_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return "youtube.com" in domain or "youtu.be" in domain


def extract_youtube_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    patterns = [
        r"(?:v=|\/v\/|embed\/|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})",
        r"v=([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_youtube_transcript(video_id: str) -> Optional[str]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        yt = YouTubeTranscriptApi()
        try:
            snippets = yt.fetch(video_id, languages=("fr", "en"))
        except Exception:
            try:
                snippets = yt.fetch(video_id)
            except Exception:
                transcripts = yt.list(video_id)
                first_t = next(iter(transcripts), None)
                if not first_t:
                    return None
                snippets = first_t.fetch()

        lines = []
        for s in snippets:
            txt = s.get("text", "") if isinstance(s, dict) else getattr(s, "text", str(s))
            if txt and txt.strip():
                lines.append(txt.strip())
        return " ".join(lines) if lines else None
    except Exception as e:
        print(f"Error fetching YouTube transcript for {video_id}: {e}")
        return None


def is_arxiv_url(url: str) -> bool:
    if not url:
        return False
    return "arxiv.org" in url.lower()


def extract_arxiv_id(url: str) -> Optional[str]:
    match = re.search(
        r"arxiv\.org\/(?:abs|pdf)\/([0-9]+\.[0-9]+(?:v[0-9]+)?|[a-zA-Z\-]+(?:\.[a-zA-Z]+)?\/[0-9]+)",
        url,
        re.IGNORECASE,
    )
    if match:
        arxiv_id = match.group(1)
        if arxiv_id.endswith(".pdf"):
            arxiv_id = arxiv_id[:-4]
        return arxiv_id
    return None


def is_pdf_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf")


def extract_pdf_text_from_bytes(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t.strip())
        return "\n\n".join(pages_text)
    except Exception as e:
        print("Error reading PDF bytes with pypdf:", e)
        return ""


def extract_pdf_metadata_and_text(pdf_bytes: bytes) -> Dict[str, str]:
    res = {"title": "", "author": "", "content": ""}
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.metadata:
            res["title"] = reader.metadata.title or ""
            res["author"] = reader.metadata.author or ""
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t.strip())
        res["content"] = "\n\n".join(pages_text)
    except Exception as e:
        print("Error extracting PDF metadata/text:", e)
    return res


def fetch_arxiv_details(url: str) -> Dict[str, str]:
    arxiv_id = extract_arxiv_id(url)
    res = {
        "title": "",
        "author": "",
        "summary": "",
        "content": "",
        "site_name": "arXiv",
        "category": "IA & Data",
    }
    if not arxiv_id:
        return res

    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        r = requests.get(abs_url, headers=headers, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            title_el = soup.find("h1", class_="title")
            if title_el:
                res["title"] = re.sub(r"^Title:\s*", "", title_el.text, flags=re.IGNORECASE).strip()

            authors_el = soup.find("div", class_="authors")
            if authors_el:
                res["author"] = re.sub(r"^Authors?:\s*", "", authors_el.text, flags=re.IGNORECASE).strip()

            abstract_el = soup.find("blockquote", class_="abstract")
            if abstract_el:
                res["summary"] = re.sub(r"^Abstract:\s*", "", abstract_el.text, flags=re.IGNORECASE).strip()
    except Exception as e:
        print("Error fetching arXiv abstract page:", e)

    try:
        pdf_res = requests.get(pdf_url, headers=headers, timeout=12)
        if pdf_res.status_code == 200 and pdf_res.content:
            pdf_text = extract_pdf_text_from_bytes(pdf_res.content)
            if pdf_text:
                res["content"] = pdf_text
    except Exception as e:
        print("Error fetching arXiv PDF content:", e)

    if not res["summary"] and res["content"]:
        res["summary"] = res["content"][:500] + "..."

    return res


def extract_full_text_from_url(url: str) -> str:
    """Extracts complete body text from a webpage URL, YouTube transcript, or PDF/arXiv paper."""
    if not url or not url.startswith("http"):
        return ""

    if is_youtube_url(url):
        vid = extract_youtube_video_id(url)
        if vid:
            transcript = get_youtube_transcript(vid)
            if transcript:
                return transcript

    if is_arxiv_url(url):
        details = fetch_arxiv_details(url)
        if details.get("content"):
            return details["content"]
        if details.get("summary"):
            return details["summary"]

    if is_pdf_url(url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and res.content:
                pdf_text = extract_pdf_text_from_bytes(res.content)
                if pdf_text:
                    return pdf_text
        except Exception as e:
            print("PDF download failed in extract_full_text_from_url:", e)

    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(downloaded, include_links=False, include_images=False)
            if extracted and len(extracted.strip()) > 100:
                return extracted.strip()
    except Exception as e:
        print("Trafilatura extraction failed:", e)

    # Fallback to BeautifulSoup
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            ct = res.headers.get("content-type", "").lower()
            if "application/pdf" in ct:
                pdf_text = extract_pdf_text_from_bytes(res.content)
                if pdf_text:
                    return pdf_text

            soup = BeautifulSoup(res.text, "html.parser")

            # Remove scripts and styles
            for s in soup(["script", "style", "nav", "footer", "header"]):
                s.decompose()

            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 30]
            if paragraphs:
                return "\n\n".join(paragraphs)
    except Exception as e:
        print("BeautifulSoup extraction failed:", e)

    return ""


def generate_ai_summary_and_tags(
    text: str, title: str = "", author: str = "", model: Optional[str] = None, is_scientific: bool = False
) -> Dict[str, Any]:
    """Generates structured AI summary and tags using Vertex AI Gemini."""
    client = get_vertex_client()
    if not client:
        return {"summary": text[:400], "tags": ["IA", "Tech"], "model_used": "fallback"}

    text_lower = text.lower()
    title_lower = title.lower()
    if not is_scientific:
        if "arxiv" in text_lower or "arxiv" in title_lower or "abstract" in text_lower[:200]:
            is_scientific = True

    if is_scientific:
        prompt = f"""Tu es un chercheur et analyste senior en IA et sciences de la donnée.
Analyse ce papier de recherche scientifique (arXiv / PDF) et génère une synthèse scientifique rigoureuse à fort impact.

Titre du papier: {title}
Auteurs: {author}
Contenu / Abstract du papier:
{text[:10000]}

Consignes pour la synthèse scientifique ("summary") :
- Rédige un résumé clair, structuré et rigoureux en français.
- Structure obligatoire en 4 puces thématiques majeures :
  • **Contexte & Problématique** : Problème scientifique/technique traité.
  • **Méthodologie & Architecture** : Approche, méthode ou innovation proposée.
  • **Résultats & Performances** : Métriques, benchmarks et performances observées.
  • **Impact & Applications** : Implications pratiques et opportunités.
- Mets en gras (**mots clés**) les notions et métriques importantes.

Réponds EXCLUSIVEMENT au format JSON valide suivant :
{{
  "summary": "• **Contexte & Problématique** : ...\n• **Méthodologie & Architecture** : ...\n• **Résultats & Performances** : ...\n• **Impact & Applications** : ...",
  "tags": ["arXiv", "Machine Learning", "Deep Learning"]
}}
"""
    else:
        prompt = f"""Tu es un expert senior en veille technologique et IA.
Analyse cet article/post et génère une synthèse structurée à fort impact.

Titre: {title}
Auteur: {author}
Contenu:
{text[:8000]}

Consignes pour le résumé ("summary") :
- Rédige un résumé clair, synthétique et captivant en français.
- Structuré en 3 à 5 puces clés (• ).
- Mets en gras (**termes clés**) les concepts, chiffres et technologies importants.

Réponds EXCLUSIVEMENT au format JSON valide suivant :
{{
  "summary": "• **Concept 1** : Explication...\n• **Chiffre / Innovation 2** : Détail...\n• **Enseignement 3** : Impact...",
  "tags": ["LLM", "Agentic AI", "DevOps"]
}}
"""

    try:
        output, model_used = generate_with_gemini(client, prompt, model)
        # Clean markdown backticks if returned
        output = re.sub(r"^```json\s*", "", output)
        output = re.sub(r"^```\s*", "", output)
        output = re.sub(r"\s*```$", "", output)

        data = json.loads(output)
        default_tags = ["arXiv", "IA"] if is_scientific else ["IA", "Tech"]
        return {
            "summary": data.get("summary", text[:400]),
            "tags": data.get("tags", default_tags),
            "model_used": model_used,
        }
    except Exception as e:
        print("AI Summary generation failed:", e)
        return {"summary": text[:400], "tags": ["Tech"], "model_used": "fallback"}


def generate_weekly_newsletter(articles: List[Dict[str, Any]], model: Optional[str] = None) -> str:
    """Generates a weekly curated AI newsletter / digest from a list of articles."""
    client = get_vertex_client()
    if not articles:
        return "# 📰 Newsletter Veille Technologique\n\nAucun article sauvegardé cette semaine."

    context_lines = []
    for i, a in enumerate(articles, 1):
        context_lines.append(
            f"[{i}] {a.get('title')} (Auteur: {a.get('author') or 'N/A'}, Catégorie: {a.get('category')})\nRésumé/Contenu: {a.get('summary') or a.get('content') or ''}\nURL: {a.get('url') or 'N/A'}\n"
        )

    context_str = "\n".join(context_lines)

    prompt = f"""Tu es un rédateur en chef spécialisé en veille technologique et IA.
Rédige une Newsletter / Digest Hebdomadaire élégante et captivante en Markdown en français basée sur les articles de veille ci-dessous :

{context_str[:12000]}

La newsletter doit être structurée ainsi :
# 📰 Newsletter Veille Tech & IA
## 💡 L'essentiel de la semaine
(Un paragraphe synthétique présentant les 2-3 grandes tendances observées)

## 🚀 Les Récapitulatifs & Pépites par Thématique
(Regroupe les posts/articles par thème avec les points clés et citations)

## 📌 À Retenir & Prochaines Éapes
(Enseignements clés pour l'équipe)

Rédige dans un style fluide, professionnel et engageant. N'invente pas de faux articles, réfère-toi uniquement aux articles fournis.
"""

    try:
        text_res, _ = generate_with_gemini(client, prompt, model)
        return text_res
    except Exception as e:
        return f"# 📰 Newsletter Veille Technologique\n\nErreur lors de la génération IA: {str(e)}"


def answer_rag_question(
    query: str,
    articles: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    web_search: bool = False,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Answers user queries across the whole knowledge base with optional Web Search grounding and conversational memory."""
    client = get_vertex_client()
    if not articles and not web_search:
        return {
            "answer": "Votre base de veille est actuellement vide. Ajoutez des articles pour pouvoir poser des questions !",
            "sources": [],
            "model_used": "none",
        }

    # Prepare knowledge base context
    kb_items = []
    for a in articles:
        text_body = a.get("summary") or a.get("content") or ""
        kb_items.append(
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "author": a.get("author"),
                "category": a.get("category"),
                "url": a.get("url"),
                "text": text_body[:1000],
            }
        )

    kb_str = json.dumps(kb_items, ensure_ascii=False, indent=2)

    # Format previous conversation history turns
    history_str = ""
    if conversation_history and len(conversation_history) > 0:
        history_lines = []
        for msg in conversation_history[-10:]:
            role = "Utilisateur" if msg.get("role") == "user" else "Assistant Synapse"
            history_lines.append(f"{role} : {msg.get('content', '')}")
        history_str = "Historique récent de la discussion en cours :\n" + "\n".join(history_lines) + "\n\n"

    if web_search:
        prompt = f"""Tu es le Chatbot IA de Veille Technologique "Synapse AI".
Tu disposes à la fois de la base de connaissances personnelle de l'utilisateur et d'un outil de recherche Google en direct.

{history_str}Base de connaissances locale de l'utilisateur (articles, posts, rapports) :
{kb_str[:12000]}

Question de l'utilisateur : "{query}"

Instructions de réponse :
1. Réponds de façon précise, synthétique et structurée en français (utilise du Markdown riche : listes à puces, gras pour les termes clés).
2. Approche HYBRIDE : Exploite en priorité les éléments de sa base de veille locale, et complète avec les dernières informations récentes et tendances du Web mondial grâce à la recherche.
3. Cites explicitement tes sources (noms d'auteurs, titres d'articles ou noms des sites web consultés).
"""
    else:
        prompt = f"""Tu es le Chatbot IA de Veille Technologique "Synapse AI".

{history_str}Base de connaissances de l'utilisateur (articles, posts LinkedIn, rapports de veille) :
{kb_str[:15000]}

Question de l'utilisateur : "{query}"

Instructions de réponse :
1. Réponds de façon précise, synthétique et structurée en français (utilise du Markdown soigné : listes à puces, gras pour les termes clés).
2. Base ta réponse en priorité sur les articles fournis dans la base de connaissances ci-dessus.
3. Cite explicitement les auteurs ou titres des articles et posts utilisés pour répondre.
4. Si la base de connaissances ne contient pas l'information requise, réponds poliment que l'information n'est pas présente dans sa veille actuelle.
"""

    try:
        sources = []
        target_model = model or GEMINI_MODEL

        if web_search and client:
            # Generate with Google Search Grounding tool
            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
            )
            answer = response.text or ""
            model_used = f"{target_model} (Web Search)"

            # Extract grounded web sources
            if response.candidates and hasattr(response.candidates[0], "grounding_metadata"):
                gm = response.candidates[0].grounding_metadata
                for chunk in getattr(gm, "grounding_chunks", []) or []:
                    if getattr(chunk, "web", None):
                        raw_uri = chunk.web.uri or ""
                        clean_url = unwrap_redirect_url(raw_uri)
                        title = chunk.web.title or "Source Web"
                        if clean_url and clean_url != "#":
                            domain = clean_url.split("/")[2].replace("www.", "") if "/" in clean_url else "Web"
                            sources.append(
                                {
                                    "id": "web",
                                    "title": title,
                                    "author": "Google Web Search",
                                    "url": clean_url,
                                    "site_name": domain,
                                    "category": "Web Mondial",
                                }
                            )
        else:
            answer, model_used = generate_with_gemini(client, prompt, model)

        # Match cited or relevant local articles
        ans_lower = answer.lower()
        q_lower = query.lower()
        for a in articles:
            t = (a.get("title") or "").lower()
            s = (a.get("summary") or "").lower()
            aut = (a.get("author") or "").lower()
            aid = str(a.get("id") or "")

            is_cited = (
                (t and (t[:25] in ans_lower or (len(t) > 10 and t[-20:] in ans_lower)))
                or (aid and (f"id {aid}" in ans_lower or f"id: {aid}" in ans_lower))
                or (aut and len(aut) > 3 and aut in ans_lower)
            )
            is_relevant = any(w in t or w in s or w in aut for w in q_lower.split() if len(w) > 3)

            if is_cited or is_relevant:
                if not any(src.get("id") == a.get("id") for src in sources):
                    sources.append(
                        {
                            "id": a.get("id"),
                            "title": a.get("title"),
                            "author": a.get("author"),
                            "url": a.get("url"),
                            "site_name": a.get("site_name") or "Veille",
                            "category": a.get("category") or "Tech & IA",
                        }
                    )

        return {"answer": answer, "sources": sources[:8], "model_used": model_used}
    except Exception as e:
        return {"answer": f"Erreur lors de l'analyse IA : {str(e)}", "sources": [], "model_used": "error"}


def answer_article_question(
    article: Dict[str, Any], query: str, model: Optional[str] = None, force_web_search: bool = False
) -> Dict[str, Any]:
    """Answers a question about a specific article using Vertex AI Gemini + Web Search if needed or forced."""
    client = get_vertex_client()
    if not client:
        return {"answer": "Service IA indisponible.", "used_web_search": False, "model_used": "none"}

    title = article.get("title", "")
    author = article.get("author", "")
    content = article.get("content") or article.get("summary") or ""

    web_context = ""
    needs_search = force_web_search or any(
        k in query.lower()
        for k in ["recherche", "web", "dernière", "actuel", "comparer", "prix", "concurrents", "2026", "news", "site"]
    )
    if needs_search and title:
        try:
            search_query = f"{title} {query}"[:100]
            search_url = f"https://html.duckduckgo.com/html/?q={quote(search_query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            res = requests.get(search_url, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                snippets = [a.get_text().strip() for a in soup.find_all("a", class_="result__snippet")[:3]]
                if snippets:
                    web_context = "\n[Résultats de recherche Web récents sur ce sujet]:\n" + "\n".join(snippets)
        except Exception as e:
            print("Web search info:", e)

    prompt = f"""Tu es un assistant IA de veille ultra-concis. L'utilisateur te pose une question spécifique sur cet article/post :

Titre: {title}
Auteur: {author or "N/A"}

Contenu complet de l'article :
{content[:12000]}
{web_context}

Question de l'utilisateur : "{query}"

Consignes de rédaction indispensables :
1. Réponds de façon ULTRA-SUCCINCTE et directe (2 à 4 puces courtes maximum).
2. Utilise uniquement des puces (• ).
3. Mets en gras (**termes clés**) uniquement les mots, concepts ou chiffres essentiels.
4. Supprime toute phrase d'introduction, de formule de politesse ou de transition ("D'après l'article...", "En résumé..."). Va directement aux puces clés.
"""

    try:
        answer, model_used = generate_with_gemini(client, prompt, model)
        return {"answer": answer, "used_web_search": bool(web_context), "model_used": model_used}
    except Exception as e:
        return {"answer": f"Erreur lors de l'analyse : {str(e)}", "used_web_search": False, "model_used": "error"}


def generate_radar_search_queries(client, entity: str) -> List[str]:
    """Generates 4 tailored search queries designed to uncover both competitive advantages and hidden limitations/controversies."""
    prompt = f"""Tu es un analyste de renseignement technologique et économique.
Nous devons sonder en profondeur l'opinion et le sentiment sur l'entité : "{entity}".
Génère 4 requêtes de recherche web complémentaires en anglais et français, ultra-ciblées pour ratisser à la fois le positif et le négatif.

Les 4 axes obligatoires :
1. Avantages concurrentiels, souveraineté, écosystème, investisseurs et forces majeures.
2. Critiques acerbes, controverses, limites techniques, déceptions des utilisateurs/développeurs.
3. Modèle économique, rentabilité, pivot stratégique (ex: service/consulting vs recherche, coûts, gouvernance).
4. Retours d'expérience concrets, benchmarks réels, discussions communauté (Hacker News, Reddit, dev).

Réponds UNIQUEMENT avec un JSON contenant une liste de 4 chaînes de caractères :
["requete 1", "requete 2", "requete 3", "requete 4"]
"""
    try:
        output, _ = generate_with_gemini(client, prompt)
        output = re.sub(r"^```json\s*", "", output)
        output = re.sub(r"^```\s*", "", output)
        output = re.sub(r"\s*```$", "", output)
        queries = json.loads(output)
        if isinstance(queries, list) and len(queries) >= 3:
            return queries[:4]
    except Exception as e:
        print("Dynamic query generation error:", e)

    return [
        f"{entity} major advantages competitive moat sovereign ecosystem",
        f"{entity} controversies critiques limitations problems complaints",
        f"{entity} business model pivot consulting risks governance",
        f"{entity} developer feedback benchmarks issues 2026",
    ]


def unwrap_redirect_url(url: str) -> str:
    """Unwraps vertexaisearch.cloud.google.com grounding redirects into clean, permanent canonical URLs."""
    if not url or "grounding-api-redirect" not in url:
        return url
    try:
        r = requests.head(url, allow_redirects=False, timeout=2)
        if r.status_code in [301, 302, 303, 307, 308] and "Location" in r.headers:
            return r.headers["Location"]
    except Exception:
        pass
    return url


def analyze_sentiment_radar(entity: str, articles: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Deep Research sentiment analysis using native Google Search grounding with canonical un-redirected sources."""
    client = get_vertex_client()
    if not client:
        return {
            "entity": entity,
            "sentiment_score": 50,
            "sentiment_label": "Neutre / IA Indisponible",
            "summary": "Analyse de sentiment indisponible.",
            "news_and_trends": "Service d'analyse indisponible.",
            "pros": [{"point": "• **Analyse** : Service IA indisponible.", "sources": []}],
            "cons": [{"point": "• **Analyse** : Service IA indisponible.", "sources": []}],
            "sources": [],
        }

    from google.genai import types

    prompt = f"""Tu es un analyste stratégique senior de haut niveau (intelligence économique et tech).
Effectue une étude d'opinion et de sentiment approfondie, objective et sans concession sur : "{entity}".
Utilise l'outil de recherche Google pour trouver les toutes dernières actualités, les débats récents, les avis de la communauté (Reddit, Hacker News, presse tech), les controverses et les points forts. Ne te base sur aucun flux interne, uniquement sur le web.

Consignes impératives pour l'analyse :
1. "sentiment_score" : Entier entre 0 et 100 (% d'avis positifs global).
2. "sentiment_label" : Libellé exact ("Très Favorable", "Plutôt Favorable", "Mitigé / Contrasté", "Plutôt Critique").
3. "summary" : Synthèse stratégique globale percutante en 2-3 phrases.
4. "news_and_trends" : Un résumé détaillé (3-4 phrases) des DERNIÈRES ACTUALITÉS récentes et de CE QUI SE DIT actuellement sur {entity} (annonces récentes, recrutements, partenariats, rumeurs ou tendances dans la communauté).
5. "pros" : 3 points forts / atouts majeurs réels et sourcés (commençant par "• **Titre** : ..."). Associe 1 ou 2 sources réelles avec leur titre.
6. "cons" : 3 limites, controverses ou aspects limitants réels et étayés (ex: modèle économique, dépendances, pivots, critiques techniques). Ne donne pas de banalité creuse. Associe 1 ou 2 sources réelles avec rel titre.

Format de réponse EXCLUSIVEMENT en JSON pur :
{{
  "entity": "{entity}",
  "sentiment_score": 70,
  "sentiment_label": "Plutôt Favorable",
  "summary": "Synthèse globale...",
  "news_and_trends": "Dernières actualités et ce qui se dit...",
  "pros": [
    {{
      "point": "• **Titre 1** : Détail...",
      "sources": [{{"title": "Nom de la source"}}]
    }}
  ],
  "cons": [
    {{
      "point": "• **Titre 1** : Détail...",
      "sources": [{{"title": "Nom de la source"}}]
    }}
  ]
}}
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
        )

        text = response.text or ""
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        data = json.loads(text)

        # Collect verified canonical web sources from grounding metadata
        grounded_sources = []
        if response.candidates and hasattr(response.candidates[0], "grounding_metadata"):
            gm = response.candidates[0].grounding_metadata
            for chunk in getattr(gm, "grounding_chunks", []) or []:
                if getattr(chunk, "web", None):
                    raw_uri = chunk.web.uri or ""
                    clean_url = unwrap_redirect_url(raw_uri)
                    title = chunk.web.title or "Source Web"
                    if clean_url and clean_url != "#":
                        grounded_sources.append({"title": title, "url": clean_url})

        # Sanitize and bind canonical URLs to pros & cons sources
        for category in ["pros", "cons"]:
            for item in data.get(category, []):
                if isinstance(item, dict):
                    sources = item.get("sources", [])
                    cleaned_sources = []
                    for s in sources:
                        url = s.get("url", "")
                        title = s.get("title", "")
                        if "grounding-api-redirect" in url:
                            url = unwrap_redirect_url(url)
                        # If URL is still a broken redirect or missing, match with a grounded source
                        if not url or "grounding-api-redirect" in url or url == "#":
                            matched = next(
                                (
                                    gs
                                    for gs in grounded_sources
                                    if gs["title"].lower() in title.lower() or title.lower() in gs["title"].lower()
                                ),
                                None,
                            )
                            if matched:
                                url = matched["url"]
                                if not title or title == "Nom de la source":
                                    title = matched["title"]
                            elif grounded_sources:
                                # Fall back to first available verified source
                                fallback_gs = grounded_sources[len(cleaned_sources) % len(grounded_sources)]
                                url = fallback_gs["url"]
                                if not title or title == "Nom de la source":
                                    title = fallback_gs["title"]
                        if url and url != "#":
                            cleaned_sources.append({"title": title or "Source Web", "url": url})
                    # If item had no sources, assign one from grounded_sources
                    if not cleaned_sources and grounded_sources:
                        fallback_gs = grounded_sources[len(cleaned_sources) % len(grounded_sources)]
                        cleaned_sources.append({"title": fallback_gs["title"], "url": fallback_gs["url"]})
                    item["sources"] = cleaned_sources

        data["sources"] = grounded_sources[:8]
        if "news_and_trends" not in data:
            data["news_and_trends"] = ""
        return data

    except Exception as e:
        print("Sentiment analysis failed:", e)
        return {
            "entity": entity,
            "sentiment_score": 50,
            "sentiment_label": "Mitigé / Analyse Partielle",
            "summary": f"Opinion globale recueillie sur {entity}.",
            "news_and_trends": f"Actualités récentes en cours de consolidation pour {entity}.",
            "evolution_note": "",
            "pros": [{"point": f"• **Intérêt** : Forte visibilité de {entity} sur le marché.", "sources": []}],
            "cons": [{"point": "• **Vigilance** : Sujet complexe nécessitant une analyse approfondie.", "sources": []}],
            "sources": [],
        }


def compare_sentiment_evolution(client, entity: str, prev_report: Dict[str, Any], new_report: Dict[str, Any]) -> str:
    """Compares a previous snapshot against a newly generated one and produces an informative evolution note."""
    if not prev_report:
        return ""

    prev_date = (prev_report.get("created_at") or "la précédente analyse")[:16].replace("T", " ")
    prev_summary = prev_report.get("summary") or ""
    prev_news = prev_report.get("news_and_trends") or ""
    new_summary = new_report.get("summary") or ""
    new_news = new_report.get("news_and_trends") or ""

    prompt = f"""Tu es un analyste de veille stratégique.
Compare la situation actuelle de "{entity}" avec son analyse précédente datant du {prev_date}.

Ancienne situation ({prev_date}) :
Résumé : {prev_summary}
Actualités : {prev_news}

Nouvelle situation actuelle :
Résumé : {new_summary}
Actualités : {new_news}

Rédige une courte note d'évolution percutante (2 à 3 phrases claires) expliquant si la situation a changé depuis la dernière prise d'information, quels événements nouveaux ont eu lieu ou si de nouvelles controverses/opportunités sont apparues. N'affiche pas de calcul mathématique ou delta numérique, décris directement les faits concrets et la dynamique d'évolution.
"""
    try:
        note, _ = generate_with_gemini(client, prompt)
        return note.strip()
    except Exception as e:
        print("Evolution comparison error:", e)
        return ""
