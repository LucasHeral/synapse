import os
import re
import sqlite3
from typing import Any, Dict, List

import sqlite_vec

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synapse_veille.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:
        print("Warning: Failed to load sqlite_vec extension:", e)
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create main articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT NOT NULL,
            summary TEXT,
            content TEXT,
            site_name TEXT,
            author TEXT,
            category TEXT DEFAULT 'Tech & IA',
            tags TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            image_url TEXT,
            is_favorite INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON articles(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")

    # Create sqlite-vec virtual table for article embeddings (384 dimensions)
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_articles USING vec0(
                article_id INTEGER PRIMARY KEY,
                embedding float[384]
            )
        """)
    except Exception as e:
        print("Warning: Failed to create vec_articles virtual table:", e)

    # Create FTS5 virtual table for full-text search and synchronization triggers
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title, summary, content, tags, notes,
                content='articles',
                content_rowid='id'
            )
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                INSERT INTO articles_fts(rowid, title, summary, content, tags, notes)
                VALUES (new.id, new.title, new.summary, new.content, new.tags, new.notes);
            END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, summary, content, tags, notes)
                VALUES('delete', old.id, old.title, old.summary, old.content, old.tags, old.notes);
            END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, summary, content, tags, notes)
                VALUES('delete', old.id, old.title, old.summary, old.content, old.tags, old.notes);
                INSERT INTO articles_fts(rowid, title, summary, content, tags, notes)
                VALUES (new.id, new.title, new.summary, new.content, new.tags, new.notes);
            END;
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO articles_fts(rowid, title, summary, content, tags, notes)
            SELECT id, title, summary, content, tags, notes FROM articles
        """)
    except Exception as e:
        print("Warning: Failed to create articles_fts virtual table or triggers:", e)

    # Create sentiment_reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL,
            sentiment_score INTEGER NOT NULL,
            sentiment_label TEXT NOT NULL,
            summary TEXT NOT NULL,
            news_and_trends TEXT DEFAULT '',
            evolution_note TEXT DEFAULT '',
            pros_json TEXT NOT NULL,
            cons_json TEXT NOT NULL,
            sources_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_date ON sentiment_reports(entity, created_at)")

    # Create chat_conversations and chat_messages tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated ON chat_conversations(updated_at DESC)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources_json TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conv ON chat_messages(conversation_id, created_at)")

    conn.commit()

    # Backfill embeddings for existing articles
    backfill_embeddings(conn)

    conn.close()


def save_article_embedding(conn, article_id: int, embedding: List[float]):
    """Saves or updates vector embedding for an article in vec_articles."""
    if not embedding:
        return
    try:
        serialized = sqlite_vec.serialize_float32(embedding)
        cursor = conn.cursor()
        cursor.execute("SELECT article_id FROM vec_articles WHERE article_id = ?", (article_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE vec_articles SET embedding = ? WHERE article_id = ?", (serialized, article_id))
        else:
            cursor.execute("INSERT INTO vec_articles(article_id, embedding) VALUES (?, ?)", (article_id, serialized))
        conn.commit()
    except Exception as e:
        print(f"Error saving embedding for article {article_id}:", e)


def delete_article_embedding(conn, article_id: int):
    """Deletes vector embedding for an article from vec_articles."""
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vec_articles WHERE article_id = ?", (article_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting embedding for article {article_id}:", e)


def backfill_embeddings(conn):
    """Computes and saves embeddings for articles that do not have vector representations yet."""
    try:
        from ai_service import compute_embedding

        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.title, a.summary, a.content, a.tags, a.notes
            FROM articles a
            LEFT JOIN vec_articles v ON a.id = v.article_id
            WHERE v.article_id IS NULL
        """)
        missing = cursor.fetchall()
        for row in missing:
            article_id = row["id"]
            text_to_embed = f"{row['title'] or ''}\n{row['summary'] or ''}\n{row['content'] or ''}\nTags: {row['tags'] or ''}\nNotes: {row['notes'] or ''}".strip()
            if text_to_embed:
                emb = compute_embedding(text_to_embed)
                if emb:
                    save_article_embedding(conn, article_id, emb)
    except Exception as e:
        print("Error during backfill_embeddings:", e)


def hybrid_search_articles(
    conn, query: str, limit: int = 50, k: int = 60, include_archived: bool = False
) -> List[Dict[str, Any]]:
    """Combines FTS5 full-text keyword search and sqlite-vec semantic vector search via RRF (Reciprocal Rank Fusion)."""
    if not query or not query.strip():
        cursor = conn.cursor()
        archived_clause = "" if include_archived else "WHERE is_archived = 0"
        cursor.execute(f"SELECT * FROM articles {archived_clause} ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]

    query_str = query.strip()
    cursor = conn.cursor()

    # 1. Full-Text Search (FTS5)
    fts_ranks = []
    try:
        fts_query = re.sub(r"[^\w\s]", " ", query_str).strip()
        if fts_query:
            formatted_fts = " ".join([f'"{w}"' for w in fts_query.split() if w])
            cursor.execute(
                "SELECT rowid FROM articles_fts WHERE articles_fts MATCH ? ORDER BY rank LIMIT ?",
                (formatted_fts, limit),
            )
            fts_ranks = [r["rowid"] for r in cursor.fetchall()]
    except Exception as e:
        print("FTS query failed:", e)

    if not fts_ranks:
        search_pattern = f"%{query_str}%"
        archived_cond = "" if include_archived else "AND is_archived = 0"
        cursor.execute(
            f"""SELECT id FROM articles
               WHERE 1=1 {archived_cond} AND (title LIKE ? OR summary LIKE ? OR content LIKE ? OR tags LIKE ? OR notes LIKE ?)
               ORDER BY created_at DESC LIMIT ?""",
            (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, limit),
        )
        fts_ranks = [r["id"] for r in cursor.fetchall()]

    # 2. Semantic Vector Search (sqlite-vec)
    vec_ranks = []
    try:
        from ai_service import compute_embedding

        q_emb = compute_embedding(query_str)
        if q_emb:
            serialized_q = sqlite_vec.serialize_float32(q_emb)
            cursor.execute(
                """
                SELECT article_id, distance
                FROM vec_articles
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
                """,
                (serialized_q, limit),
            )
            vec_ranks = [r["article_id"] for r in cursor.fetchall()]
    except Exception as e:
        print("Vector query failed:", e)

    # 3. Reciprocal Rank Fusion (RRF)
    scores = {}
    for rank, doc_id in enumerate(fts_ranks, 1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    for rank, doc_id in enumerate(vec_ranks, 1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    if not scores:
        archived_clause = "" if include_archived else "WHERE is_archived = 0"
        cursor.execute(f"SELECT * FROM articles {archived_clause} ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]

    sorted_doc_ids = [doc_id for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)]

    # Fetch full article records maintaining RRF score ordering
    placeholders = ",".join(["?"] * len(sorted_doc_ids))
    archived_cond = "" if include_archived else "AND is_archived = 0"
    cursor.execute(
        f"SELECT * FROM articles WHERE id IN ({placeholders}) {archived_cond}",
        sorted_doc_ids,
    )
    articles_by_id = {row["id"]: dict(row) for row in cursor.fetchall()}

    results = []
    for doc_id in sorted_doc_ids:
        if doc_id in articles_by_id:
            results.append(articles_by_id[doc_id])

    return results[:limit]


def migrate_remove_url_not_null():
    if not os.path.exists(DB_PATH):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS articles_new (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, title TEXT NOT NULL, summary TEXT, content TEXT, site_name TEXT, author TEXT, category TEXT DEFAULT 'Tech & IA', tags TEXT DEFAULT '', notes TEXT DEFAULT '', image_url TEXT, is_favorite INTEGER DEFAULT 0, is_archived INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        cursor.execute("INSERT OR IGNORE INTO articles_new SELECT * FROM articles")
        cursor.execute("DROP TABLE articles")
        cursor.execute("ALTER TABLE articles_new RENAME TO articles")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON articles(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
        conn.commit()
        print("Schema migration completed: url column is now nullable!")
    except Exception as e:
        print("Migration info:", e)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    migrate_remove_url_not_null()
