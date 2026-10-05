import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest  # noqa: E402

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import init_db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_stats_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "favorites" in data
        assert "categories_count" in data


def test_articles_list_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/articles")
        assert response.status_code == 200
        articles = response.json()
        assert isinstance(articles, list)


def test_categories_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/categories")
        assert response.status_code == 200
        categories = response.json()
        assert isinstance(categories, list)


def test_auto_detect_category():
    from main import auto_detect_category

    assert auto_detect_category("https://linkedin.com/feed") == "LinkedIn"
    assert auto_detect_category("https://github.com/vllm-project", title="LLM Agent") in [
        "IA & Data",
        "Tech & IA",
        "Dev & Tech",
    ]


def test_classify_category_zero_shot_standard(monkeypatch):
    from ai_service import classify_category_zero_shot

    mock_client = MagicMock()
    monkeypatch.setattr("ai_service.get_vertex_client", lambda: mock_client)
    monkeypatch.setattr(
        "ai_service.generate_with_gemini", lambda client, prompt, model=None: ("IA & Data", "gemini-2.5-flash")
    )

    category = classify_category_zero_shot(
        url="https://example.com/article",
        title="Nouveau modèle de langage LLM Open Source",
        summary="Découverte des performances exceptionnelles.",
    )
    assert category == "IA & Data"


def test_classify_category_zero_shot_dynamic_novel_topic(monkeypatch):
    from ai_service import classify_category_zero_shot

    mock_client = MagicMock()
    monkeypatch.setattr("ai_service.get_vertex_client", lambda: mock_client)
    monkeypatch.setattr(
        "ai_service.generate_with_gemini",
        lambda client, prompt, model=None: ("Biotech & Santé", "gemini-2.5-flash"),
    )

    category = classify_category_zero_shot(
        url="https://example.com/dna-editing",
        title="CRISPR v2: Séquençage génétique rapide",
        summary="Thérapie génique et médecine de précision.",
    )
    assert category == "Biotech & Santé"


def test_classify_category_zero_shot_fallback(monkeypatch):
    from ai_service import classify_category_zero_shot

    # 1. Fallback when Gemini client is None
    monkeypatch.setattr("ai_service.get_vertex_client", lambda: None)

    cat_linkedin = classify_category_zero_shot(url="https://linkedin.com/posts/123", site_name="LinkedIn")
    assert cat_linkedin == "LinkedIn"

    cat_dev = classify_category_zero_shot(url="https://github.com/repo", title="Python Framework")
    assert cat_dev == "Dev & Tech"

    # 2. Fallback when Gemini API call raises an exception
    mock_client = MagicMock()
    monkeypatch.setattr("ai_service.get_vertex_client", lambda: mock_client)

    def mock_raise(*args, **kwargs):
        raise RuntimeError("API error")

    monkeypatch.setattr("ai_service.generate_with_gemini", mock_raise)

    cat_fallback = classify_category_zero_shot(url="https://example.com/test", title="Random Subject")
    assert cat_fallback == "Général"


def test_sentiment_report_save_and_get():
    with TestClient(app) as client:
        payload = {
            "entity": "OpenAI",
            "sentiment_score": 80,
            "sentiment_label": "Très Positif",
            "summary": "Excellente réputation sur la recherche IA.",
            "pros": ["• **Innovation** : Modèles de pointe."],
            "cons": ["• **Coût** : Tarification des APIs."],
            "sources": [],
        }
        res_save = client.post("/api/sentiment/reports", json=payload)
        assert res_save.status_code in [200, 201]

        res_get = client.get("/api/sentiment/reports/OpenAI")
        assert res_get.status_code == 200
        data = res_get.json()
        assert data["entity"] == "OpenAI"
        assert data["sentiment_score"] == 80


def test_youtube_ingestion_helpers():
    from ai_service import extract_youtube_video_id, is_youtube_url

    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert is_youtube_url(yt_url) is True
    assert extract_youtube_video_id(yt_url) == "dQw4w9WgXcQ"

    short_url = "https://youtu.be/dQw4w9WgXcQ"
    assert is_youtube_url(short_url) is True
    assert extract_youtube_video_id(short_url) == "dQw4w9WgXcQ"


def test_arxiv_pdf_ingestion_helpers():
    from ai_service import extract_arxiv_id, is_arxiv_url, is_pdf_url

    arxiv_url = "https://arxiv.org/abs/2301.00001"
    assert is_arxiv_url(arxiv_url) is True
    assert extract_arxiv_id(arxiv_url) == "2301.00001"

    pdf_url = "https://example.com/paper.pdf"
    assert is_pdf_url(pdf_url) is True


def test_extract_youtube_endpoint(monkeypatch):
    def mock_transcript(video_id):
        return f"Transcribed video content for {video_id}"

    monkeypatch.setattr("main.get_youtube_transcript", mock_transcript)

    with TestClient(app) as client:
        res = client.post("/api/extract", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        assert res.status_code == 200
        data = res.json()
        assert data["site_name"] == "YouTube"
        assert "dQw4w9WgXcQ" in data["content"]


def test_extract_arxiv_endpoint(monkeypatch):
    def mock_arxiv(url):
        return {
            "title": "Attention Is All You Need",
            "author": "Ashish Vaswani et al.",
            "summary": "We propose the Transformer, a novel neural network architecture...",
            "content": "Full paper content about Transformers and self-attention mechanisms.",
            "site_name": "arXiv",
            "category": "IA & Data",
        }

    monkeypatch.setattr("main.fetch_arxiv_details", mock_arxiv)

    with TestClient(app) as client:
        res = client.post("/api/extract", json={"url": "https://arxiv.org/abs/1706.03762"})
        assert res.status_code == 200
        data = res.json()
        assert data["site_name"] == "arXiv"
        assert data["title"] == "Attention Is All You Need"
        assert data["category"] == "IA & Data"
        assert "Transformer" in data["content"]


def test_pdf_parsing_with_pypdf():
    import io

    from ai_service import extract_pdf_metadata_and_text, extract_pdf_text_from_bytes
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": "Test Scientific Paper", "/Author": "Alice & Bob"})

    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    meta = extract_pdf_metadata_and_text(pdf_bytes)
    assert meta["title"] == "Test Scientific Paper"
    assert meta["author"] == "Alice & Bob"

    text = extract_pdf_text_from_bytes(pdf_bytes)
    assert isinstance(text, str)


def test_extract_pdf_endpoint(monkeypatch):
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": "Deep Learning Survey", "/Author": "Yann LeCun"})
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    class MockResponse:
        status_code = 200
        content = pdf_bytes

    monkeypatch.setattr("requests.get", lambda url, headers=None, timeout=None: MockResponse())

    with TestClient(app) as client:
        res = client.post("/api/extract", json={"url": "https://example.com/deep_learning.pdf"})
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Deep Learning Survey"
        assert data["author"] == "Yann LeCun"
        assert data["site_name"] == "PDF"


def test_scientific_ai_summary_fallback():
    from ai_service import generate_ai_summary_and_tags

    res = generate_ai_summary_and_tags(
        text="Abstract: We present a novel deep learning framework...",
        title="Deep Learning Framework",
        author="Researcher",
        is_scientific=True,
    )
    assert "summary" in res
    assert "tags" in res
    assert isinstance(res["tags"], list)


def test_hybrid_search():
    from database import get_db_connection, hybrid_search_articles

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO articles (title, summary, content, category) VALUES (?, ?, ?, ?)",
        (
            "Machine Learning Vector Search",
            "In-depth guide on RRF and embeddings.",
            "Full text content about vector databases.",
            "IA & Data",
        ),
    )
    conn.commit()

    results = hybrid_search_articles(conn, "Vector Search", limit=10)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert any("Vector Search" in r["title"] for r in results)


def test_compute_embedding():
    from ai_service import compute_embedding

    emb = compute_embedding("Intelligence Artificielle et Vector Search")
    assert emb is not None
    assert isinstance(emb, list)
    assert len(emb) == 384


def test_create_article_with_embedding():
    with TestClient(app) as client:
        article_data = {
            "url": "https://example.com/vector-db-test",
            "title": "Database sqlite-vec et recherche hybride",
            "summary": "Mise en place de sqlite-vec pour les embeddings vectoriels.",
            "content": "Aperçu de la recherche vectorielle avec sqlite-vec et FTS5.",
            "category": "IA & Data",
            "tags": "vector, sqlite-vec, rrf",
        }
        response = client.post("/api/articles", json=article_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == article_data["title"]
        art_id = data["id"]

        from database import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT article_id FROM vec_articles WHERE article_id = ?", (art_id,))
        vec_row = cursor.fetchone()
        assert vec_row is not None
        assert vec_row["article_id"] == art_id
        conn.close()


def test_search_endpoints_hybrid():
    with TestClient(app) as client:
        # 1. Test GET /api/search?q=...
        res1 = client.get("/api/search?q=sqlite-vec")
        assert res1.status_code == 200
        articles = res1.json()
        assert isinstance(articles, list)

        # 2. Test GET /api/articles?search=...
        res2 = client.get("/api/articles?search=vector")
        assert res2.status_code == 200
        articles_search = res2.json()
        assert isinstance(articles_search, list)


def test_ai_chat_endpoint_with_hybrid_search():
    with TestClient(app) as client:
        payload = {"query": "Comment fonctionne la recherche vectorielle ?", "web_search": False}
        res = client.post("/api/ai/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert "conversation_id" in data


def test_article_permalink_endpoint():
    with TestClient(app) as client:
        create_payload = {
            "title": "Article Test Permalink",
            "url": "https://example.com/article-test-permalink",
            "summary": "Résumé de l'article de test permalink.",
            "category": "Tech & IA",
            "site_name": "Example",
            "author": "Auteur Test",
        }
        res_create = client.post("/api/articles", json=create_payload)
        assert res_create.status_code == 200
        created = res_create.json()
        article_id = created["id"]

        res_get = client.get(f"/api/articles/{article_id}")
        assert res_get.status_code == 200
        data = res_get.json()
        assert data["id"] == article_id
        assert data["title"] == "Article Test Permalink"
        assert "permalink" in data
        assert data["permalink"] == f"/?article={article_id}"
        assert "share_metadata" in data
        assert data["share_metadata"]["title"] == "Article Test Permalink"
        assert data["share_metadata"]["permalink"] == f"/?article={article_id}"


def test_article_permalink_not_found():
    with TestClient(app) as client:
        res_get = client.get("/api/articles/999999")
        assert res_get.status_code == 404
        data = res_get.json()
        assert data["detail"] == "Article introuvable"


def test_whatsapp_inbox_and_sync():
    with TestClient(app) as client:
        # Ingest a simulated WhatsApp message
        post_res = client.post(
            "/api/ingestion/whatsapp",
            json={
                "sender": "Lucas",
                "text": "Regarde ce repo super intéressant : https://github.com/fastapi/fastapi",
                "group": "SYNAPSE",
            },
        )
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["status"] == "received"

        # Now trigger sync
        sync_res = client.get("/api/whatsapp/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "success"
        assert "processed_messages" in sync_data


def test_github_and_instagram_helpers():
    from ingestion_services import is_github_repo_url, is_instagram_url

    assert is_github_repo_url("https://github.com/tiangolo/fastapi") is True
    assert is_github_repo_url("https://github.com/tiangolo/fastapi/issues/123") is False
    assert is_github_repo_url("https://google.com") is False

    assert is_instagram_url("https://www.instagram.com/reel/C3x9Zabc/") is True
    assert is_instagram_url("https://instagram.com/p/C3x9Zabc/") is True
    assert is_instagram_url("https://twitter.com") is False
