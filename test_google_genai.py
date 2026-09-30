import google.auth
from google import genai

try:
    credentials, project_id = google.auth.default()
    print("Credentials loaded successfully. Project ID:", project_id)

    # Initialize client for Vertex AI
    client = genai.Client(vertexai=True, project=project_id, location="us-central1")

    response = client.models.generate_content(model="gemini-2.5-flash", contents="Dis bonjour en 3 mots.")
    print("Vertex AI Gemini Response:", response.text)
except Exception as e:
    print("GenAI Error:", e)
