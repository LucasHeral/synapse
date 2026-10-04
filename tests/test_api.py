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
