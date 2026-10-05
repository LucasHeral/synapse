import json
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List

import requests

FFMPEG_PATH = "/Users/lucas.heral/.hermes/tools/ffmpeg-9.0.1-darwin-arm64/ffmpeg"
if os.path.exists(FFMPEG_PATH):
    os.environ["PATH"] = f"{os.path.dirname(FFMPEG_PATH)}:{os.environ.get('PATH', '')}"


# ==========================================
# 1. GITHUB REPOSITORY INGESTION & KPIS
# ==========================================


def is_github_repo_url(url: str) -> bool:
    """Checks if a URL points to a GitHub repository."""
    if not url:
        return False
    clean = url.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "")
    if not clean.startswith("github.com/"):
        return False
    parts = [p for p in clean.split("/")[1:] if p and not p.startswith("?")]
    if len(parts) == 2 and parts[0] not in [
        "explore",
        "topics",
        "trending",
        "marketplace",
        "settings",
        "pricing",
        "features",
        "search",
        "notifications",
        "orgs",
        "users",
    ]:
        return True
    return False


def fetch_github_repo_details(url: str) -> Dict[str, Any]:
    """Fetches GitHub repository metadata (stars, forks, language, license) and full README."""
    clean = url.strip().replace("https://", "").replace("http://", "").replace("www.", "")
    parts = [p for p in clean.split("/")[1:] if p and not p.startswith("?")]
    owner = parts[0]
    repo = parts[1]

    headers = {
        "User-Agent": "Synapse-Intelligence/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    # Optional GitHub token for higher rate limits if set
    gh_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_data = {}
    try:
        r = requests.get(api_url, headers=headers, timeout=8)
        if r.status_code == 200:
            repo_data = r.json()
    except Exception as e:
        print(f"Erreur API GitHub pour {owner}/{repo}: {e}")

    # Fetch official full README
    readme_text = ""
    for branch in ["HEAD", "main", "master"]:
        try:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            r_readme = requests.get(raw_url, headers=headers, timeout=8)
            if r_readme.status_code == 200 and r_readme.text:
                readme_text = r_readme.text
                break
        except Exception:
            continue

    stars = repo_data.get("stargazers_count", 0)
    forks = repo_data.get("forks_count", 0)
    language = repo_data.get("language") or "Code"
    license_name = (repo_data.get("license") or {}).get("spdx_id") or "Open Source"
    description = repo_data.get("description") or f"Dépôt GitHub de {owner}/{repo}"
    topics = repo_data.get("topics", [])

    # Format stars string (e.g. 14.2k)
    stars_str = f"{stars / 1000:.1f}k" if stars >= 1000 else str(stars)
    forks_str = f"{forks / 1000:.1f}k" if forks >= 1000 else str(forks)

    # Detect category based on topics and description
    content_lower = f"{description} {' '.join(topics)}".lower()
    is_ai = any(
        kw in content_lower
        for kw in ["ai", "llm", "agent", "gpt", "rag", "deep learning", "machine learning", "neural"]
    )
    category = "IA & Data" if is_ai else "Dev & Tech"

    # Clean structured summary
    summary = f"⭐ **{stars_str} stars** · 🍴 **{forks_str} forks** · 💻 **{language}** · ⚖️ **{license_name}**\n\n{description}"

    # Package metadata in notes field for display
    github_kpis = {
        "is_github": True,
        "stars": stars,
        "stars_str": stars_str,
        "forks": forks,
        "forks_str": forks_str,
        "language": language,
        "license": license_name,
        "topics": topics,
    }

    return {
        "url": f"https://github.com/{owner}/{repo}",
        "title": f"{owner}/{repo} : {description[:80]}",
        "author": owner,
        "site_name": "GitHub",
        "summary": summary,
        "content": readme_text or description,
        "category": category,
        "tags": ", ".join(topics[:5]) if topics else language,
        "notes": json.dumps(github_kpis),
    }


# ==========================================
# 2. INSTAGRAM REELS EXTRACTION & TRANSCRIPT
# ==========================================


def is_instagram_url(url: str) -> bool:
    """Checks if a URL points to an Instagram reel or post."""
    if not url:
        return False
    lower = url.lower()
    return "instagram.com/reel/" in lower or "instagram.com/reels/" in lower or "instagram.com/p/" in lower


def transcribe_instagram_reel_with_gemini(audio_path: str, url: str) -> Dict[str, Any]:
    """Sends audio to Vertex AI Gemini 2.5 Flash for multimodal speech-to-text and structuring."""
    from ai_service import GEMINI_MODEL, get_vertex_client
    from google.genai import types

    client = get_vertex_client()
    if not client:
        return {
            "transcript": "Audio extrait mais client Vertex AI non disponible.",
            "title": "Reel Instagram",
            "summary": "Audio extrait.",
            "creator": "Instagram",
            "category": "Tech & IA",
        }

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3")

    prompt = """Tu es un expert en veille technologique et transcription audio/vidéo.
Écoute attentivement cet extrait audio d'un Reel Instagram de veille technologique.

Instructions :
1. Transcris fidèlement et intégralement tout ce qui est dit mot pour mot dans la langue d'origine (français ou anglais).
2. Fournis un titre clair, percutant et informatif résumant le sujet technique abordé.
3. Rédige un résumé structuré sous forme de bullet points avec les concepts clés en gras.
4. Identifie le créateur ou l'auteur si mentionné dans l'audio.
5. Détermine la catégorie appropriée (ex: "Tech & IA", "Dev & Tech", "Business & SaaS").

Réponds UNIQUEMENT sous forme de JSON valide avec cette structure exacte :
{
  "transcript": "Transcription intégrale mot à mot...",
  "title": "Titre explicite de la vidéo...",
  "summary": "• Point clé 1...\n• Point clé 2...",
  "creator": "Nom ou pseudo du créateur",
  "category": "Tech & IA"
}
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt, part],
        )
        text = response.text or ""
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        return json.loads(text)
    except Exception as e:
        print(f"Erreur transcription Gemini Audio: {e}")
        return {
            "transcript": f"Transcription audio en échec: {str(e)}",
            "title": "Reel Instagram",
            "summary": "Impossible de transcrire l'audio du Reel via Gemini.",
            "creator": "Instagram",
            "category": "Tech & IA",
        }


def extract_instagram_reel(url: str) -> Dict[str, Any]:
    """Downloads reel audio via yt-dlp and transcribes spoken content using Gemini."""
    os.makedirs("/tmp/synapse_media", exist_ok=True)
    temp_dir = tempfile.mkdtemp(dir="/tmp/synapse_media")
    audio_output = os.path.join(temp_dir, "reel_audio.mp3")

    # Clean URL query params
    clean_url = url.split("?")[0]

    # Run yt-dlp to extract audio
    cmd = [
        "/Users/lucas.heral/.hermes/worktrees/synapse-ingestion/.venv/bin/yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--output",
        audio_output,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
    ]
    if os.path.exists(FFMPEG_PATH):
        cmd.extend(["--ffmpeg-location", FFMPEG_PATH])

    cmd.append(clean_url)

    audio_extracted = False
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if res.returncode == 0 and (
            os.path.exists(audio_output) or os.path.exists(audio_output.replace(".mp3", "") + ".mp3")
        ):
            audio_extracted = True
    except Exception as e:
        print(f"Erreur yt-dlp pour Instagram: {e}")

    # Find the generated audio file
    actual_audio = audio_output
    if not os.path.exists(actual_audio):
        files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith(".mp3") or f.endswith(".m4a")]
        if files:
            actual_audio = files[0]
            audio_extracted = True

    if audio_extracted and os.path.exists(actual_audio):
        analysis = transcribe_instagram_reel_with_gemini(actual_audio, clean_url)
        # Cleanup temp file
        try:
            os.remove(actual_audio)
            os.rmdir(temp_dir)
        except Exception:
            pass

        return {
            "url": clean_url,
            "title": analysis.get("title") or "Reel Instagram",
            "author": analysis.get("creator") or "Instagram Creator",
            "site_name": "Instagram",
            "summary": analysis.get("summary") or "Transcription de Reel Instagram",
            "content": analysis.get("transcript") or "",
            "category": analysis.get("category") or "Tech & IA",
            "tags": "Instagram, Reel, Vidéo",
        }
    else:
        # Fallback: scrape page metadata via requests
        return {
            "url": clean_url,
            "title": "Post Instagram",
            "author": "Instagram",
            "site_name": "Instagram",
            "summary": "Post Instagram (audio non extrait).",
            "content": f"Lien vers le post Instagram: {clean_url}",
            "category": "Tech & IA",
            "tags": "Instagram",
        }


# ==========================================
# 3. WHATSAPP INBOX & AUTO-SYNC ENGINE
# ==========================================

URL_REGEX = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')


def extract_urls_from_text(text: str) -> List[str]:
    """Finds all URLs inside a text message."""
    if not text:
        return []
    urls = URL_REGEX.findall(text)
    clean_urls = []
    for u in urls:
        clean = u.rstrip(".,;!?:)]}'\"")
        if clean.startswith("www."):
            clean = "https://" + clean
        if clean not in clean_urls:
            clean_urls.append(clean)
    return clean_urls


def process_whatsapp_incoming_message(sender: str, message_text: str, group_name: str = "SYNAPSE") -> Dict[str, Any]:
    """Processes an incoming message from the WhatsApp SYNAPSE group and ingests detected links."""
    from database import get_db_connection

    urls = extract_urls_from_text(message_text)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Record message in whatsapp_inbox
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

    cursor.execute(
        "INSERT INTO whatsapp_inbox (group_name, sender, message_text, urls_json) VALUES (?, ?, ?, ?)",
        (group_name, sender, message_text, json.dumps(urls)),
    )
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"message_id": msg_id, "urls_found": urls}
