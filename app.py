import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("LIBRARY_DB_PATH", str(APP_DIR / "library.db")))
GEMINI_MODEL = "gemini-2.5-flash"

st.set_page_config(page_title="Library Management System", page_icon="📚", layout="wide")


@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database():
    with database() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT UNIQUE,
                category TEXT NOT NULL DEFAULT 'General',
                quantity INTEGER NOT NULL CHECK(quantity >= 1),
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                borrower_name TEXT NOT NULL,
                borrower_contact TEXT,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                return_date TEXT,
                FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_loans_book_return
            ON loans(book_id, return_date);

            CREATE INDEX IF NOT EXISTS idx_loans_due_return
            ON loans(due_date, return_date);
        """)


def list_books(search_text="", category="All"):
    sql = """
        SELECT
            b.id, b.title, b.author, b.isbn, b.category, b.quantity,
            b.quantity - (
                SELECT COUNT(*)
                FROM loans AS l
                WHERE l.book_id = b.id AND l.return_date IS NULL
            ) AS available,
            (
                SELECT COUNT(*)
                FROM loans AS l
                WHERE l.book_id = b.id AND l.return_date IS NULL
            ) AS borrowed
        FROM books AS b
        WHERE (
            b.title LIKE ? OR
            b.author LIKE ? OR
            COALESCE(b.isbn, '') LIKE ?
        )
    """
    params = [f"%{search_text}%", f"%{search_text}%", f"%{search_text}%"]

    if category != "All":
        sql += " AND b.category = ?"
        params.append(category)

    sql += " ORDER BY b.title COLLATE NOCASE"

    with database() as conn:
        return conn.execute(sql, params).fetchall()

