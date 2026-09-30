import json
import os
import re
from typing import Any, Dict, List, Optional

import google.auth
import requests
import trafilatura
from bs4 import BeautifulSoup
from google import genai

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
_vertex_client = None


def get_vertex_client():
    global _vertex_client
    if _vertex_client is not None:
        return _vertex_client

    try:
        credentials, project_id = google.auth.default()
        _vertex_client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        return _vertex_client
    except Exception as e:
        print("Error initializing Vertex AI Client:", e)
        return None


def generate_with_gemini(client, prompt: str, requested_model: Optional[str] = None):
    """Generates content using requested model with fallback to available Gemini Flash models."""
    models_to_try = [
        m for m in [requested_model, GEMINI_MODEL, "gemini-3.8-flash", "gemini-2.5-flash", "gemini-1.5-flash"] if m
    ]

    seen = set()
    unique_models = []
    for m in models_to_try:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)

    last_error = None
    for model_name in unique_models:
        try:
            res = client.models.generate_content(model=model_name, contents=prompt)
            return res.text.strip(), model_name
        except Exception as e:
            last_error = e
            print(f"Model {model_name} failed, trying fallback...", e)

    raise last_error or Exception("All Gemini models failed.")


def extract_full_text_from_url(url: str) -> str:
    """Extracts complete body text from a webpage URL using trafilatura or BeautifulSoup."""
    if not url or not url.startswith("http"):
        return ""

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
    text: str, title: str = "", author: str = "", model: Optional[str] = None
) -> Dict[str, Any]:
    """Generates structured AI summary and tags using Vertex AI Gemini."""
    client = get_vertex_client()
    if not client:
        return {"summary": text[:400], "tags": ["IA", "Tech"], "model_used": "fallback"}

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
        return {
            "summary": data.get("summary", text[:400]),
            "tags": data.get("tags", ["IA", "Tech"]),
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


def answer_rag_question(query: str, articles: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
    """Answers user queries across the whole knowledge base using Vertex AI Gemini with cited sources."""
    client = get_vertex_client()
    if not articles:
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

    prompt = f"""Tu es le Chatbot IA de Veille Technologique "Synapse AI".
Voici l'ensemble de la base de connaissance de l'utilisateur (articles, posts LinkedIn, actus) :

{kb_str[:15000]}

Question de l'utilisateur : "{query}"

Instructions :
1. Réponds de façon précise, synthétique et structurée en français.
2. Basé TOUTE ta réponse sur les articles fournis dans la base de connaissance.
3. Cite explicitement les auteurs ou titres des posts utilisés pour répondre.
4. Si la base de connaissance ne contient pas l'information requise, réponds poliment que l'information n'est pas présente dans sa veille actuelle.
"""

    try:
        answer, model_used = generate_with_gemini(client, prompt, model)

        # Identify relevant sources
        sources = []
        q_lower = query.lower()
        for a in articles:
            t = (a.get("title") or "").lower()
            s = (a.get("summary") or "").lower()
            aut = (a.get("author") or "").lower()
            if any(w in t or w in s or w in aut for w in q_lower.split() if len(w) > 3):
                sources.append(
                    {"id": a.get("id"), "title": a.get("title"), "author": a.get("author"), "url": a.get("url")}
                )

        return {"answer": answer, "sources": sources[:5], "model_used": model_used}
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
            search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(search_query)}"
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
