import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synapse_veille.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create table without NOT NULL on url
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

    conn.commit()
    conn.close()


def migrate_remove_url_not_null():
    if not os.path.exists(DB_PATH):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Recreate table without NOT NULL on url
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
