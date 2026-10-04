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
