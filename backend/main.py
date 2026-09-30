import os
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

import requests
from ai_service import (
    answer_article_question,
    answer_rag_question,
    extract_full_text_from_url,
    generate_ai_summary_and_tags,
    generate_weekly_newsletter,
)
from bs4 import BeautifulSoup
from database import get_db_connection, init_db
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from models import ArticleCreate, ArticleUpdate, ExtractRequest
from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    model: Optional[str] = None


class ArticleChatRequest(BaseModel):
    article_id: int
    query: str
    model: Optional[str] = None
    force_web_search: Optional[bool] = False


class NewsletterRequest(BaseModel):
    days: Optional[int] = 7
    model: Optional[str] = None


class EnrichRequest(BaseModel):
    model: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SYNAPSE API",
    description="API REST officielle de SYNAPSE - Hub de Veille Technologique & IA avec Google Vertex AI Gemini 3.8 Flash & Extension Chrome V3",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for Chrome Extension & local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def auto_detect_category(url: str, title: str = "", summary: str = "", site_name: str = "") -> str:
    text = f"{title} {summary} {url} {site_name}".lower()

    if "linkedin.com" in url.lower() or "linkedin" in site_name.lower():
        return "LinkedIn"
    if any(
        k in text
        for k in ["ai", "ia", "llm", "gpt", "claude", "gemini", "machine learning", "deep learning", "neural", "prompt"]
    ):
        return "IA & Data"
    if any(
        k in text
        for k in [
            "python",
            "javascript",
            "react",
            "vue",
            "code",
            "dev",
            "github",
            "api",
            "architecture",
            "backend",
            "frontend",
            "rust",
        ]
    ):
        return "Dev & Tech"
    if any(
        k in text for k in ["business", "startup", "vc", "saaS", "marketing", "finance", "strategy", "mrr", "growth"]
    ):
        return "Business & SaaS"
    if any(k in text for k in ["design", "ui", "ux", "css", "figma"]):
        return "Design & UX"
    if any(k in text for k in ["cybersecurity", "security", "privacy", "hack"]):
        return "Sécurité"

    return "Général"


@app.post("/api/extract")
def extract_metadata(req: ExtractRequest):
    url = req.url
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    extracted = {
        "url": url,
        "title": "",
        "summary": "",
        "site_name": "",
        "author": "",
        "image_url": "",
        "category": "Tech & IA",
    }

    try:
        domain = urlparse(url).netloc.replace("www.", "")
        extracted["site_name"] = domain.capitalize()

        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract title
            og_title = soup.find("meta", property="og:title") or soup.find("meta", {"name": "twitter:title"})
            if og_title and og_title.get("content"):
                extracted["title"] = og_title["content"].strip()
            elif soup.title and soup.title.text:
                extracted["title"] = soup.title.text.strip()
            else:
                extracted["title"] = domain

            # Extract description / summary
            og_desc = (
                soup.find("meta", property="og:description")
                or soup.find("meta", {"name": "description"})
                or soup.find("meta", {"name": "twitter:description"})
            )
            if og_desc and og_desc.get("content"):
                extracted["summary"] = og_desc["content"].strip()

            # Extract site name
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                extracted["site_name"] = og_site["content"].strip()

            # Extract image
            og_image = soup.find("meta", property="og:image") or soup.find("meta", {"name": "twitter:image"})
            if og_image and og_image.get("content"):
                extracted["image_url"] = og_image["content"].strip()

            # Extract author
            meta_author = soup.find("meta", {"name": "author"}) or soup.find("meta", property="article:author")
            if meta_author and meta_author.get("content"):
                extracted["author"] = meta_author["content"].strip()

    except Exception as e:
        extracted["title"] = extracted["url"]
        extracted["summary"] = f"Extraction automatique impossible: {str(e)}"

    extracted["category"] = auto_detect_category(
        extracted["url"], extracted["title"], extracted["summary"], extracted["site_name"]
    )

    return extracted


@app.post("/api/articles")
def create_article(article: ArticleCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    tags_str = article.tags
    if isinstance(tags_str, list):
        tags_str = ", ".join([t.strip() for t in tags_str if t.strip()])

    article_url = article.url.strip() if (article.url and article.url.strip()) else None

    # Auto-extract site_name domain if empty
    site_name = article.site_name.strip() if article.site_name else ""
    if not site_name and article_url:
        try:
            from urllib.parse import urlparse

            domain = urlparse(article_url).netloc.replace("www.", "")
            parts = domain.split(".")
            if parts[0]:
                site_name = parts[0].capitalize() + "." + ".".join(parts[1:])
            else:
                site_name = domain.capitalize()
        except Exception:
            site_name = "Web"

    # Auto-fetch full page text if content is empty or short
    content = article.content.strip() if article.content else ""
    if article_url and len(content) < 100 and article_url.startswith("http"):
        try:
            extracted_text = extract_full_text_from_url(article_url)
            if extracted_text and len(extracted_text) > len(content):
                content = extracted_text
        except Exception:
            pass

    # Check if category is empty/default, auto-detect if needed
    category = article.category or "Général"
    if category in ["Général", "Tech & IA", ""]:
        category = auto_detect_category(article_url or "", article.title, article.summary, site_name)

    article_id = None

    if article_url:
        cursor.execute("SELECT id FROM articles WHERE url = ?", (article_url,))
        existing = cursor.fetchone()
        if existing:
            article_id = existing["id"]
            cursor.execute(
                """
                UPDATE articles
                SET title = ?, summary = ?, content = ?, site_name = ?, category = ?, tags = ?, notes = ?, image_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (
                    article.title,
                    article.summary or "",
                    content,
                    site_name,
                    category,
                    tags_str or "",
                    article.notes or "",
                    article.image_url or "",
                    article_id,
                ),
            )
            conn.commit()

    if not article_id:
        cursor.execute(
            """
            INSERT INTO articles (url, title, summary, content, site_name, author, category, tags, notes, image_url, is_favorite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                article_url,
                article.title,
                article.summary or "",
                content,
                site_name,
                article.author or "",
                category,
                tags_str or "",
                article.notes or "",
                article.image_url or "",
                1 if article.is_favorite else 0,
            ),
        )
        conn.commit()
        article_id = cursor.lastrowid

    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    res = dict(row) if row else {}
    conn.close()
    return res


@app.post("/api/ai/enrich/{article_id}")
def ai_enrich_article(article_id: int, req: Optional[EnrichRequest] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Article introuvable")

    article = dict(row)
    url = article.get("url")
    content = article.get("content") or ""
    summary = article.get("summary") or ""
    title = article.get("title") or ""
    author = article.get("author") or ""
    req_model = req.model if req else None

    if url and url.startswith("http") and len(content.strip()) < 100:
        extracted_text = extract_full_text_from_url(url)
        if extracted_text:
            content = extracted_text

    text_for_ai = content if len(content.strip()) > 100 else summary
    if not text_for_ai:
        text_for_ai = title

    ai_res = generate_ai_summary_and_tags(text_for_ai, title=title, author=author, model=req_model)

    new_summary = ai_res.get("summary", summary)
    tags_list = ai_res.get("tags", [])
    tags_str = ", ".join(tags_list)

    cursor.execute(
        """
        UPDATE articles
        SET summary = ?, content = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (new_summary, content, tags_str, article_id),
    )
    conn.commit()

    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    updated_res = dict(cursor.fetchone())
    conn.close()
    return updated_res


@app.post("/api/ai/newsletter")
def generate_newsletter_endpoint(req: Optional[NewsletterRequest] = None):
    days = req.days if req else 7
    req_model = req.model if req else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM articles
        WHERE is_archived = 0
          AND created_at >= datetime('now', ?)
        ORDER BY created_at DESC
    """,
        (f"-{days} days",),
    )
    rows = [dict(r) for r in cursor.fetchall()]

    if len(rows) < 3:
        cursor.execute("SELECT * FROM articles WHERE is_archived = 0 ORDER BY created_at DESC LIMIT 20")
        rows = [dict(r) for r in cursor.fetchall()]

    conn.close()

    markdown_res = generate_weekly_newsletter(rows, model=req_model)
    return {"newsletter_markdown": markdown_res, "articles_count": len(rows)}


@app.post("/api/ai/chat")
def chat_kb_endpoint(req: ChatRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE is_archived = 0 ORDER BY created_at DESC LIMIT 50")
    articles = [dict(r) for r in cursor.fetchall()]
    conn.close()

    res = answer_rag_question(req.query, articles, model=req.model)
    return res


@app.post("/api/ai/article-chat")
def article_chat_endpoint(req: ArticleChatRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE id = ?", (req.article_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Article introuvable")

    article = dict(row)
    res = answer_article_question(article, req.query, model=req.model, force_web_search=bool(req.force_web_search))
    return res


@app.get("/api/articles")
def list_articles(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    favorite: Optional[bool] = None,
    archived: Optional[bool] = False,
    limit: int = 100,
    offset: int = 0,
):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM articles WHERE is_archived = ?"
    params = [1 if archived else 0]

    if category and category != "Tous":
        query += " AND category = ?"
        params.append(category)

    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag}%")

    if favorite is not None:
        query += " AND is_favorite = ?"
        params.append(1 if favorite else 0)

    if search:
        search_pattern = f"%{search}%"
        query += " AND (title LIKE ? OR summary LIKE ? OR site_name LIKE ? OR notes LIKE ? OR tags LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern, search_pattern])

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


@app.get("/api/categories")
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM articles
        WHERE is_archived = 0
        GROUP BY category
        ORDER BY count DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM articles WHERE is_archived = 0")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as favorites FROM articles WHERE is_favorite = 1 AND is_archived = 0")
    favorites = cursor.fetchone()["favorites"]

    cursor.execute("SELECT COUNT(DISTINCT category) as categories_count FROM articles WHERE is_archived = 0")
    categories_count = cursor.fetchone()["categories_count"]

    conn.close()
    return {"total": total, "favorites": favorites, "categories_count": categories_count}


@app.get("/api/articles/{article_id}")
def get_article(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Article introuvable")
    return dict(row)


@app.patch("/api/articles/{article_id}")
def update_article(article_id: int, update: ArticleUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Article introuvable")

    fields = []
    params = []

    data = update.dict(exclude_unset=True)
    for key, val in data.items():
        if key == "tags" and isinstance(val, list):
            val = ", ".join([t.strip() for t in val if t.strip()])
        if key in ["is_favorite", "is_archived"] and isinstance(val, bool):
            val = 1 if val else 0
        fields.append(f"{key} = ?")
        params.append(val)

    if fields:
        fields.append("updated_at = CURRENT_TIMESTAMP")
        sql = f"UPDATE articles SET {', '.join(fields)} WHERE id = ?"
        params.append(article_id)
        cursor.execute(sql, params)
        conn.commit()

    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    updated_row = dict(cursor.fetchone())
    conn.close()
    return updated_row


@app.delete("/api/articles/{article_id}")
def delete_article(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Article {article_id} supprimé"}


# Serve static dashboard UI
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Synapse AI Backend Active. Front-end loading..."}
