import sys
from pathlib import Path

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
    assert "Vector Search" in results[0]["title"]


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
