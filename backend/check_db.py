import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().with_name("roadmap.db")

if not DB_FILE.exists():
    print("Database file not found.")
else:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("SELECT id, name, created_at FROM roadmaps")
        rows = c.fetchall()
        if not rows:
            print("No roadmaps found.")
        else:
            print(f"Found {len(rows)} roadmaps:")
            for row in rows:
                print(f"ID: {row['id']}, Name: '{row['name']}'")
    except Exception as e:
        print(f"Error reading database: {e}")
    finally:
        conn.close()
