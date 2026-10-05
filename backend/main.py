import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from ai_service import (
    analyze_sentiment_radar,
    answer_article_question,
    answer_rag_question,
    classify_category_zero_shot,
    compare_sentiment_evolution,
    compute_embedding,
    extract_full_text_from_url,
    extract_pdf_metadata_and_text,
    extract_youtube_video_id,
    fetch_arxiv_details,
    generate_ai_summary_and_tags,
    generate_weekly_newsletter,
    get_vertex_client,
    get_youtube_transcript,
    is_arxiv_url,
    is_pdf_url,
    is_youtube_url,
)
from bs4 import BeautifulSoup
from database import (
    delete_article_embedding,
    get_db_connection,
    hybrid_search_articles,
    init_db,
    save_article_embedding,
)
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from models import ArticleCreate, ArticleUpdate, ExtractRequest, SentimentReportCreate
from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[int] = None
    model: Optional[str] = None
    web_search: Optional[bool] = False


class ChatConversationCreate(BaseModel):
    title: Optional[str] = "Nouvelle conversation"


class ChatConversationUpdate(BaseModel):
    title: str


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


class SentimentRequest(BaseModel):
    entity: str


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
    return classify_category_zero_shot(url=url, title=title, summary=summary, site_name=site_name)


@app.post("/api/extract")
def extract_metadata(req: ExtractRequest):
    url = req.url
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # Special Handling: GitHub Repositories (Stars, Forks, Language, Full README)
    from ingestion_services import (
        extract_instagram_reel,
        fetch_github_repo_details,
        is_github_repo_url,
        is_instagram_url,
    )

    if is_github_repo_url(url):
        try:
            return fetch_github_repo_details(url)
        except Exception as e:
            print("GitHub repo fetch error:", e)

    # Special Handling: Instagram Reels & Posts (Audio Extraction & Gemini Transcription)
    if is_instagram_url(url):
        try:
            return extract_instagram_reel(url)
        except Exception as e:
            print("Instagram reel fetch error:", e)

    # 1. YouTube handling
    if is_youtube_url(url):
        video_id = extract_youtube_video_id(url)
        video_title = None
        video_author = ""
        video_thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""
        video_desc = ""

        # 1. Fetch metadata via YouTube official open oEmbed API (Never blocked, fast < 50ms)
        if video_id:
            try:
                oembed_url = (
                    f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                )
                oembed_res = requests.get(oembed_url, timeout=5)
                if oembed_res.status_code == 200:
                    oembed_data = oembed_res.json()
                    if oembed_data.get("title"):
                        video_title = oembed_data["title"].strip()
                    if oembed_data.get("author_name"):
                        video_author = oembed_data["author_name"].strip()
                    if oembed_data.get("thumbnail_url"):
                        video_thumbnail = oembed_data["thumbnail_url"]
            except Exception as e:
                print("YouTube oEmbed fetch error:", e)

        # 2. Fallback to yt-dlp if title is missing
        if not video_title:
            try:
                import yt_dlp

                ydl_opts = {
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        t_val = info.get("title")
                        if t_val:
                            video_title = str(t_val).strip()
                        u_val = info.get("uploader")
                        if u_val and not video_author:
                            video_author = str(u_val).strip()
                        d_val = info.get("description")
                        if d_val and not video_desc:
                            video_desc = str(d_val)[:500]
                        th_val = info.get("thumbnail")
                        if th_val and not video_thumbnail:
                            video_thumbnail = str(th_val)
            except Exception as e:
                print("yt-dlp YouTube info fallback error:", e)

        # 3. Retrieve full transcript
        transcript = get_youtube_transcript(video_id) if video_id else None

        summary = video_desc
        if transcript:
            summary = f"Transcript de la vidéo :\n{transcript[:600]}..." if not summary else summary

        extracted = {
            "url": url,
            "title": video_title or "Vidéo YouTube",
            "summary": summary,
            "content": transcript or "",
            "site_name": "YouTube",
            "author": video_author or "YouTube",
            "image_url": video_thumbnail,
            "category": "Tech & IA",
        }

        extracted["category"] = auto_detect_category(
            extracted["url"], extracted["title"], extracted["summary"], extracted["site_name"]
        )
        return extracted

    # 2. arXiv handling
    if is_arxiv_url(url):
        details = fetch_arxiv_details(url)
        extracted = {
            "url": url,
            "title": details.get("title") or "Papier arXiv",
            "summary": details.get("summary") or "",
            "content": details.get("content") or "",
            "site_name": "arXiv",
            "author": details.get("author") or "",
            "image_url": "",
            "category": "IA & Data",
        }
        extracted["category"] = auto_detect_category(
            extracted["url"], extracted["title"], extracted["summary"], extracted["site_name"]
        )
        return extracted

    # 3. Direct PDF handling
    if is_pdf_url(url):
        extracted = {
            "url": url,
            "title": "Document PDF",
            "summary": "",
            "content": "",
            "site_name": "PDF",
            "author": "",
            "image_url": "",
            "category": "Tech & IA",
        }
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and res.content:
                pdf_meta = extract_pdf_metadata_and_text(res.content)
                extracted["content"] = pdf_meta.get("content", "")
                if pdf_meta.get("title"):
                    extracted["title"] = pdf_meta["title"]
                else:
                    filename = url.split("/")[-1]
                    extracted["title"] = filename or "Document PDF"
                if pdf_meta.get("author"):
                    extracted["author"] = pdf_meta["author"]
                extracted["summary"] = extracted["content"][:500] + "..." if extracted["content"] else "Document PDF"
        except Exception as e:
            extracted["summary"] = f"Extraction PDF impossible: {str(e)}"

        extracted["category"] = auto_detect_category(
            extracted["url"], extracted["title"], extracted["summary"], extracted["site_name"]
        )
        return extracted

    # 4. Standard HTML Webpages
    extracted = {
        "url": url,
        "title": "",
        "summary": "",
        "content": "",
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


@app.get("/api/whatsapp/sync")
def sync_whatsapp_inbox_endpoint():
    """Syncs un-processed WhatsApp messages from the SYNAPSE group and ingests new links."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT DEFAULT 'SYNAPSE',
            sender TEXT,
            message_text TEXT,
            urls_json TEXT,
            is_processed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT * FROM whatsapp_inbox WHERE is_processed = 0 ORDER BY created_at ASC")
    pending = [dict(r) for r in cursor.fetchall()]

    ingested_articles = []
    for p in pending:
        urls = json.loads(p.get("urls_json") or "[]")
        for u in urls:
            cursor.execute("SELECT id FROM articles WHERE url = ?", (u,))
            if not cursor.fetchone():
                try:
                    meta = extract_metadata(ExtractRequest(url=u))
                    cursor.execute(
                        """
                        INSERT INTO articles (url, title, summary, content, site_name, author, category, tags, notes, image_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            meta.get("url"),
                            meta.get("title") or u,
                            meta.get("summary") or "",
                            meta.get("content") or "",
                            meta.get("site_name") or "WhatsApp",
                            meta.get("author") or "WhatsApp",
                            meta.get("category") or "Tech & IA",
                            meta.get("tags") or "",
                            meta.get("notes") or "",
                            meta.get("image_url") or "",
                        ),
                    )
                    conn.commit()
                    ingested_articles.append(meta.get("title") or u)
                except Exception as e:
                    print(f"Erreur ingestion lien WhatsApp {u}: {e}")

        cursor.execute("UPDATE whatsapp_inbox SET is_processed = 1 WHERE id = ?", (p["id"],))
        conn.commit()

    conn.close()
    return {
        "status": "success",
        "processed_messages": len(pending),
        "ingested_count": len(ingested_articles),
        "ingested_titles": ingested_articles,
    }


@app.post("/api/ingestion/whatsapp")
def receive_whatsapp_message(payload: Dict[str, Any]):
    """Receives a new WhatsApp message (from bridge daemon or webhook) and stores it in the inbox."""
    from ingestion_services import process_whatsapp_incoming_message

    sender = payload.get("sender") or payload.get("From") or "Moi"
    message_text = payload.get("text") or payload.get("Body") or payload.get("message") or ""
    group_name = payload.get("group") or "SYNAPSE"

    res = process_whatsapp_incoming_message(sender, message_text, group_name)
    return {"status": "received", "data": res}


def background_article_enrichment_and_embedding(
    article_id: int, article_url: Optional[str], content: str, title: str, summary: str, tags: str, notes: str
):
    """Background task to extract full page text if missing and compute vector embedding."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if article_url and len(content) < 100 and article_url.startswith("http"):
            try:
                extracted_text = extract_full_text_from_url(article_url)
                if extracted_text and len(extracted_text) > len(content):
                    content = extracted_text
                    cursor.execute("UPDATE articles SET content = ? WHERE id = ?", (content, article_id))
                    conn.commit()
            except Exception as e:
                print("Background text extraction failed:", e)

        # For YouTube URLs: ensure transcript is fetched if content is empty
        if article_url and is_youtube_url(article_url) and not content:
            vid = extract_youtube_video_id(article_url)
            if vid:
                t = get_youtube_transcript(vid)
                if t:
                    content = t
                    cursor.execute("UPDATE articles SET content = ? WHERE id = ?", (content, article_id))
                    conn.commit()

        text_to_embed = f"{title}\n{summary}\n{content}\nTags: {tags}\nNotes: {notes}".strip()
        if text_to_embed:
            try:
                emb = compute_embedding(text_to_embed)
                if emb:
                    save_article_embedding(conn, article_id, emb)
            except Exception as e:
                print("Failed to save article embedding:", e)
    finally:
        conn.close()


@app.post("/api/articles")
def create_article(article: ArticleCreate, background_tasks: BackgroundTasks):
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

    content = article.content.strip() if article.content else ""

    # Special Handling: YouTube URLs when title or transcript is missing on save
    if article_url and is_youtube_url(article_url):
        vid = extract_youtube_video_id(article_url)
        # 1. Title fallback via oEmbed
        if not article.title or article.title.strip() in ["", "Vidéo YouTube", article_url]:
            if vid:
                try:
                    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
                    o_res = requests.get(oembed_url, timeout=5)
                    if o_res.status_code == 200:
                        real_t = o_res.json().get("title")
                        if real_t:
                            article.title = str(real_t).strip()
                except Exception as e:
                    print("Error fetching real YouTube title on save:", e)

        # 2. Thumbnail fallback
        if not article.image_url and vid:
            article.image_url = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"

        # 3. Retrieve transcript if content is empty
        if not content and vid:
            t = get_youtube_transcript(vid)
            if t:
                content = t
                if not article.summary or len(article.summary) < 20:
                    article.summary = f"Transcript de la vidéo :\n{t[:600]}..."

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

    # Asynchronously process heavy background tasks (instant sub-10ms response)
    if article_id:
        if background_tasks is not None:
            background_tasks.add_task(
                background_article_enrichment_and_embedding,
                article_id,
                article_url,
                content,
                article.title,
                article.summary or "",
                tags_str or "",
                article.notes or "",
            )
        else:
            background_article_enrichment_and_embedding(
                article_id,
                article_url,
                content,
                article.title,
                article.summary or "",
                tags_str or "",
                article.notes or "",
            )

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

    # Only attempt extraction if not LinkedIn and content is empty
    if (
        url
        and url.startswith("http")
        and "linkedin.com" not in url
        and len(content.strip()) < 50
        and len(summary.strip()) < 50
    ):
        try:
            extracted_text = extract_full_text_from_url(url)
            if extracted_text:
                content = extracted_text
        except Exception:
            pass

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

    # Re-compute and update vector embedding
    text_to_embed = f"{title}\n{new_summary}\n{content}\nTags: {tags_str}".strip()
    if text_to_embed:
        try:
            emb = compute_embedding(text_to_embed)
            if emb:
                save_article_embedding(conn, article_id, emb)
        except Exception as e:
            print("Failed to update article embedding after enrichment:", e)

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


@app.get("/api/chat/conversations")
def get_conversations_endpoint():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, COUNT(m.id) as message_count
        FROM chat_conversations c
        LEFT JOIN chat_messages m ON c.id = m.conversation_id
        GROUP BY c.id
        ORDER BY c.updated_at DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


@app.post("/api/chat/conversations")
def create_conversation_endpoint(req: ChatConversationCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_conversations (title) VALUES (?)",
        (req.title or "Nouvelle conversation",),
    )
    conn.commit()
    conv_id = cursor.lastrowid
    cursor.execute("SELECT * FROM chat_conversations WHERE id = ?", (conv_id,))
    conv = dict(cursor.fetchone())
    conv["messages"] = []
    conn.close()
    return conv


@app.get("/api/chat/conversations/{conversation_id}")
def get_conversation_details_endpoint(conversation_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_conversations WHERE id = ?", (conversation_id,))
    conv_row = cursor.fetchone()
    if not conv_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    conv = dict(conv_row)
    cursor.execute(
        "SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,),
    )
    messages = []
    for r in cursor.fetchall():
        m = dict(r)
        m["sources"] = json.loads(m.get("sources_json") or "[]")
        messages.append(m)
    conv["messages"] = messages
    conn.close()
    return conv


@app.delete("/api/chat/conversations/{conversation_id}")
def delete_conversation_endpoint(conversation_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM chat_conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Conversation supprimée"}


@app.post("/api/ai/chat")
def chat_kb_endpoint(req: ChatRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    conv_id = req.conversation_id
    if not conv_id:
        title = req.query.strip().replace("\n", " ")[:40]
        cursor.execute("INSERT INTO chat_conversations (title) VALUES (?)", (title or "Nouvelle discussion",))
        conn.commit()
        conv_id = cursor.lastrowid

    # Record user message in DB
    cursor.execute(
        "INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (conv_id, req.query),
    )
    conn.commit()

    # Retrieve conversation history
    cursor.execute(
        "SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conv_id,),
    )
    history = [dict(r) for r in cursor.fetchall()]

    # Fetch knowledge base articles using hybrid search (FTS + sqlite-vec vector search)
    articles = hybrid_search_articles(conn, req.query, limit=30, include_archived=False)

    # Supplement with recent articles if hybrid search returned few results
    existing_ids = {a["id"] for a in articles if isinstance(a.get("id"), int)}
    cursor.execute("SELECT * FROM articles WHERE is_archived = 0 ORDER BY created_at DESC LIMIT 20")
    for r in cursor.fetchall():
        d = dict(r)
        if d["id"] not in existing_ids:
            articles.append(d)
            existing_ids.add(d["id"])

    # Also include saved sentiment reports in RAG context
    cursor.execute("SELECT * FROM sentiment_reports ORDER BY updated_at DESC LIMIT 20")
    for r in cursor.fetchall():
        d = dict(r)
        pros_raw = json.loads(d.get("pros_json") or "[]")
        cons_raw = json.loads(d.get("cons_json") or "[]")
        pros = "\n".join([p.get("point", str(p)) if isinstance(p, dict) else str(p) for p in pros_raw])
        cons = "\n".join([c.get("point", str(c)) if isinstance(c, dict) else str(c) for c in cons_raw])
        articles.append(
            {
                "id": f"radar-{d['id']}",
                "title": f"Rapport d'opinion : {d['entity']} ({d['sentiment_score']}% - {d['sentiment_label']})",
                "site_name": "Radar d'Opinion",
                "author": "SYNAPSE Deep Research",
                "summary": d.get("summary") or "",
                "content": f"Résumé : {d.get('summary')}\n\nPoints Forts :\n{pros}\n\nPoints Faibles :\n{cons}",
                "url": f"/?radar={d['entity']}",
            }
        )

    res = answer_rag_question(
        req.query,
        articles,
        conversation_history=history,
        web_search=bool(req.web_search),
        model=req.model,
    )

    # Save assistant message & sources in DB
    cursor.execute(
        "INSERT INTO chat_messages (conversation_id, role, content, sources_json) VALUES (?, 'assistant', ?, ?)",
        (conv_id, res.get("answer", ""), json.dumps(res.get("sources", []))),
    )
    cursor.execute("UPDATE chat_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()

    res["conversation_id"] = conv_id
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


@app.post("/api/ai/sentiment")
def sentiment_radar_endpoint(req: SentimentRequest):
    entity_clean = req.entity.strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch latest previous snapshot for this entity (if any)
    cursor.execute(
        """
        SELECT * FROM sentiment_reports
        WHERE LOWER(entity) = LOWER(?)
        ORDER BY created_at DESC LIMIT 1
        """,
        (entity_clean,),
    )
    prev_row = cursor.fetchone()
    prev_report = dict(prev_row) if prev_row else None

    # 2. Analyze fresh from scratch with Google Search grounding
    res = analyze_sentiment_radar(entity_clean)

    # 3. If previous snapshot exists, compare evolution
    evolution_note = ""
    client = get_vertex_client()
    if prev_report and client:
        evolution_note = compare_sentiment_evolution(client, entity_clean, prev_report, res)
    res["evolution_note"] = evolution_note

    # 4. AUTO-SAVE snapshot to SQLite database
    pros_json = json.dumps(res.get("pros") or [], ensure_ascii=False)
    cons_json = json.dumps(res.get("cons") or [], ensure_ascii=False)
    sources_json = json.dumps(res.get("sources") or [], ensure_ascii=False)

    cursor.execute(
        """
        INSERT INTO sentiment_reports (entity, sentiment_score, sentiment_label, summary, news_and_trends, evolution_note, pros_json, cons_json, sources_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_clean,
            res.get("sentiment_score", 50),
            res.get("sentiment_label", "Neutre"),
            res.get("summary", ""),
            res.get("news_and_trends", ""),
            evolution_note,
            pros_json,
            cons_json,
            sources_json,
        ),
    )
    snapshot_id = cursor.lastrowid
    conn.commit()

    # 5. Fetch all historical snapshots for date selector
    cursor.execute(
        """
        SELECT id, created_at, sentiment_score, sentiment_label
        FROM sentiment_reports
        WHERE LOWER(entity) = LOWER(?)
        ORDER BY created_at DESC
        """,
        (entity_clean,),
    )
    snapshots = [dict(s) for s in cursor.fetchall()]
    conn.close()

    res["id"] = snapshot_id
    res["available_snapshots"] = snapshots
    return res


@app.post("/api/sentiment/reports")
def save_sentiment_report(req: SentimentReportCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    pros_json = json.dumps(req.pros or [], ensure_ascii=False)
    cons_json = json.dumps(req.cons or [], ensure_ascii=False)
    sources_json = json.dumps(req.sources or [], ensure_ascii=False)

    cursor.execute(
        """
        INSERT INTO sentiment_reports (entity, sentiment_score, sentiment_label, summary, news_and_trends, evolution_note, pros_json, cons_json, sources_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req.entity.strip(),
            req.sentiment_score,
            req.sentiment_label,
            req.summary,
            req.news_and_trends or "",
            req.evolution_note or "",
            pros_json,
            cons_json,
            sources_json,
        ),
    )
    report_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM sentiment_reports WHERE id = ?", (report_id,))
    row = dict(cursor.fetchone())
    conn.close()

    row["pros"] = json.loads(row.get("pros_json") or "[]")
    row["cons"] = json.loads(row.get("cons_json") or "[]")
    row["sources"] = json.loads(row.get("sources_json") or "[]")
    return row


@app.get("/api/sentiment/reports")
def list_sentiment_reports():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sentiment_reports ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    entities_map = {}
    for r in rows:
        d = dict(r)
        d["pros"] = json.loads(d.get("pros_json") or "[]")
        d["cons"] = json.loads(d.get("cons_json") or "[]")
        d["sources"] = json.loads(d.get("sources_json") or "[]")

        e_key = d["entity"].strip().lower()
        if e_key not in entities_map:
            entities_map[e_key] = {
                "entity": d["entity"],
                "latest_snapshot": d,
                "snapshots_count": 0,
                "snapshots": [],
            }
        entities_map[e_key]["snapshots_count"] += 1
        entities_map[e_key]["snapshots"].append(
            {
                "id": d["id"],
                "created_at": d["created_at"],
                "sentiment_score": d["sentiment_score"],
                "sentiment_label": d["sentiment_label"],
            }
        )

    return list(entities_map.values())


@app.get("/api/sentiment/reports/{entity}")
def get_sentiment_report(entity: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sentiment_reports WHERE LOWER(entity) = LOWER(?) ORDER BY created_at DESC LIMIT 1",
        (entity.strip(),),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Rapport non trouvé")

    res = dict(row)
    res["pros"] = json.loads(res.get("pros_json") or "[]")
    res["cons"] = json.loads(res.get("cons_json") or "[]")
    res["sources"] = json.loads(res.get("sources_json") or "[]")

    cursor.execute(
        "SELECT id, created_at, sentiment_score, sentiment_label FROM sentiment_reports WHERE LOWER(entity) = LOWER(?) ORDER BY created_at DESC",
        (entity.strip(),),
    )
    res["available_snapshots"] = [dict(s) for s in cursor.fetchall()]
    conn.close()
    return res


@app.get("/api/sentiment/reports/snapshot/{snapshot_id}")
def get_sentiment_snapshot(snapshot_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sentiment_reports WHERE id = ?", (snapshot_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Snapshot introuvable")

    res = dict(row)
    res["pros"] = json.loads(res.get("pros_json") or "[]")
    res["cons"] = json.loads(res.get("cons_json") or "[]")
    res["sources"] = json.loads(res.get("sources_json") or "[]")

    cursor.execute(
        "SELECT id, created_at, sentiment_score, sentiment_label FROM sentiment_reports WHERE LOWER(entity) = LOWER(?) ORDER BY created_at DESC",
        (res["entity"].strip(),),
    )
    res["available_snapshots"] = [dict(s) for s in cursor.fetchall()]
    conn.close()
    return res


@app.delete("/api/sentiment/reports/{report_id}")
def delete_sentiment_report(report_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sentiment_reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "id": report_id}


@app.delete("/api/sentiment/reports/entity/{entity}")
def delete_sentiment_entity_reports(entity: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sentiment_reports WHERE LOWER(entity) = LOWER(?)", (entity.strip(),))
    conn.commit()
    conn.close()
    return {"status": "success", "entity": entity}


@app.get("/api/search")
def search_articles_endpoint(q: str, limit: int = 50, archived: bool = False):
    conn = get_db_connection()
    results = hybrid_search_articles(conn, q, limit=limit, include_archived=archived)
    conn.close()
    return results


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

    if search:
        results = hybrid_search_articles(conn, search, limit=limit + offset, include_archived=archived or False)
        filtered = []
        for a in results:
            if category and category != "Tous" and a.get("category") != category:
                continue
            if tag and tag not in (a.get("tags") or ""):
                continue
            if favorite is not None and bool(a.get("is_favorite")) != favorite:
                continue
            filtered.append(a)
        conn.close()
        return filtered[offset : offset + limit]

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
    res = dict(row)
    res["permalink"] = f"/?article={article_id}"
    res["share_metadata"] = {
        "title": res.get("title", ""),
        "summary": res.get("summary", ""),
        "site_name": res.get("site_name", ""),
        "author": res.get("author", ""),
        "category": res.get("category", ""),
        "url": res.get("url", ""),
        "permalink": f"/?article={article_id}",
    }
    return res


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

    # Re-compute and update vector embedding
    text_to_embed = f"{updated_row.get('title') or ''}\n{updated_row.get('summary') or ''}\n{updated_row.get('content') or ''}\nTags: {updated_row.get('tags') or ''}\nNotes: {updated_row.get('notes') or ''}".strip()
    if text_to_embed:
        try:
            emb = compute_embedding(text_to_embed)
            if emb:
                save_article_embedding(conn, article_id, emb)
        except Exception as e:
            print("Failed to update embedding on article update:", e)

    conn.close()
    return updated_row


@app.delete("/api/articles/{article_id}")
def delete_article(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    delete_article_embedding(conn, article_id)
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
