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
