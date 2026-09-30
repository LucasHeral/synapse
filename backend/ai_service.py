import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import google.auth
import requests
import trafilatura
from bs4 import BeautifulSoup
from google import genai

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
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


def analyze_sentiment_radar(entity: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deep Research sentiment analysis: generates dynamic multi-faceted queries, extracts rich web evidence, and synthesizes nuanced pros/cons."""
    client = get_vertex_client()
    if not client:
        return {
            "entity": entity,
            "sentiment_score": 50,
            "sentiment_label": "Neutre / IA Indisponible",
            "summary": "Analyse de sentiment indisponible.",
            "pros": ["• **Analyse** : Service IA indisponible."],
            "cons": ["• **Analyse** : Service IA indisponible."],
            "sources": [],
        }

    # 1. Gather context from internal watch feed
    internal_snippets = []
    e_lower = entity.lower()
    matching_articles = []
    for a in articles:
        t = (a.get("title") or "").lower()
        s = (a.get("summary") or "").lower()
        c = (a.get("content") or "").lower()
        if e_lower in t or e_lower in s or e_lower in c:
            matching_articles.append(a)
            internal_snippets.append(f"- [{a.get('site_name') or 'Veille'}] {a.get('title')}: {s[:300]}")

    # 2. Dynamic Deep Research Web Queries (positive + adversarial negative)
    search_queries = generate_radar_search_queries(client, entity)
    web_sources_list = []
    seen_urls = set()

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    # Add internal matching articles to candidate sources
    for i, a in enumerate(matching_articles[:4], 1):
        web_sources_list.append(
            {
                "id": len(web_sources_list) + 1,
                "title": a.get("title") or "Article Veille",
                "url": a.get("url") or f"http://127.0.0.1:8000/?article={a.get('id')}",
                "snippet": (a.get("summary") or a.get("content") or "")[:400],
                "type": "Veille locale",
            }
        )

    for sq in search_queries:
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={quote(sq)}"
            res = requests.get(search_url, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                results = soup.find_all("div", class_="result__body")
                for r in results[:4]:
                    snippet_el = r.find("a", class_="result__snippet")
                    title_el = r.find("a", class_="result__a") or r.find("a", class_="result__url")
                    if snippet_el and title_el:
                        url = title_el.get("href")
                        title = title_el.get_text().strip()
                        snippet = snippet_el.get_text().strip()
                        if url and url not in seen_urls and len(snippet) > 20:
                            seen_urls.add(url)
                            web_sources_list.append(
                                {
                                    "id": len(web_sources_list) + 1,
                                    "title": title[:100],
                                    "url": url,
                                    "snippet": snippet,
                                    "type": "Web",
                                }
                            )
        except Exception as e:
            print(f"Search error for query '{sq}':", e)

    # Format numbered sources context for Gemini
    sources_text_block = "\n".join(
        [f"[{s['id']}] {s['title']} ({s['url']}) :\n{s['snippet']}" for s in web_sources_list[:16]]
    )

    prompt = f"""Tu es un analyste stratégique senior de haut niveau (type cabinet d'intelligence économique et analyste tech).
Tu effectues une étude d'opinion et d'impact rigoureuse, sans concession et nuancée sur : "{entity}".

Voici les sources contextuelles issues de l'investigation contradictoire (veille locale + web pros/cons/controverses) :
{sources_text_block[:12000]}

Consignes impératives pour l'analyse :
1. "sentiment_score" : Un entier entre 0 et 100 reflétant la balance globale d'opinion (ex: 60 = 60% positif / 40% négatif).
2. "sentiment_label" : Libellé exact en français (ex: "Très Favorable", "Plutôt Favorable", "Mitigé / Contrasté", "Plutôt Critique").
3. "summary" : Un résumé stratégique percutant en français (3 phrases riches) mettant en avant la tension principale entre ses atouts majeurs et ses réels défis.
4. "pros" : 3 points forts / atouts majeurs réels et sourcés. Sois concret (ex: souveraineté européenne, appuis institutionnels/politiques, performance technique mesurée, adoption industrielle). Pour CHAQUE point fort, associe 1 ou 2 sources réelles issues de la liste ci-dessus avec leur titre et url.
5. "cons" : 3 limites, controverses ou aspects limitants MAJEURS et réalistes. Les points limitants doivent être précis et étayés (ex: dérive vers du consulting/service au détriment de la R&D pure, manque de transparence, dépendance infrastructurelle, gouvernance contestée, réticences communauté). Ne sors JAMAIS de banalité creuse comme "marché compétitif" ou "doit faire ses preuves". Pour CHAQUE point faible, associe 1 ou 2 sources réelles issues de la liste ci-dessus avec leur titre et url.

Format de réponse OBLIGATOIRE en JSON pur :
{{
  "entity": "{entity}",
  "sentiment_score": 65,
  "sentiment_label": "Plutôt Favorable",
  "summary": "Synthèse stratégique...",
  "pros": [
    {{
      "point": "• **Titre 1** : Détail factuel...",
      "sources": [
        {{"title": "Titre source", "url": "https://..."}}
      ]
    }}
  ],
  "cons": [
    {{
      "point": "• **Titre 1** : Détail factuel...",
      "sources": [
        {{"title": "Titre source", "url": "https://..."}}
      ]
    }}
  ]
}}
"""

    try:
        output, model_used = generate_with_gemini(client, prompt)
        output = re.sub(r"^```json\s*", "", output)
        output = re.sub(r"^```\s*", "", output)
        output = re.sub(r"\s*```$", "", output)

        data = json.loads(output)
        data["sources"] = web_sources_list[:8]
        return data
    except Exception as e:
        print("Sentiment analysis failed:", e)
        return {
            "entity": entity,
            "sentiment_score": 50,
            "sentiment_label": "Mitigé / Analyse Partielle",
            "summary": f"Opinion globale recueillie sur {entity}.",
            "pros": [f"• **Intérêt** : Forte visibilité de {entity} sur le marché."],
            "cons": ["• **Vigilance** : Sujet complexe nécessitant une analyse approfondie."],
            "sources": [],
        }
