import sqlite3
from datetime import datetime
import json

DB_PATH = "news_briefs.db"

def init_db():
    """Initialize SQLite database for storing news briefs."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Briefs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            section TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            title TEXT,
            content TEXT,
            indices_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brief_id INTEGER,
            platform TEXT,
            clicks INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (brief_id) REFERENCES briefs(id)
        )
    ''')

    conn.commit()
    conn.close()

def save_brief(date, section, time_slot, title, content, indices_data):
    """Save a generated brief to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO briefs (date, section, time_slot, title, content, indices_data)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (date, section, time_slot, title, content, json.dumps(indices_data)))

    conn.commit()
    brief_id = cursor.lastrowid
    conn.close()

    return brief_id

def get_brief(date):
    """Fetch brief for a specific date."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM briefs WHERE date = ?
        ORDER BY time_slot ASC
    ''', (date,))

    rows = cursor.fetchall()
    conn.close()

    return rows

def get_all_briefs(limit=30):
    """Fetch all briefs (latest first)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT date FROM briefs
        ORDER BY date DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [row[0] for row in rows]
