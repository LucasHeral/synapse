import google.auth
from google import genai


def test_vertex_genai_ping():
    try:
        credentials, project_id = google.auth.default()
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        response = client.models.generate_content(model="gemini-2.5-flash", contents="Dis bonjour en 3 mots.")
        assert response.text is not None
        assert len(response.text.strip()) > 0
    except Exception as e:
        print("Vertex AI ADC info:", e)
