import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def test_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "favorites" in data
    assert "categories_count" in data


def test_articles_list_endpoint():
    response = client.get("/api/articles")
    assert response.status_code == 200
    articles = response.json()
    assert isinstance(articles, list)


def test_categories_endpoint():
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
