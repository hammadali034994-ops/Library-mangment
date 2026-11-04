import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("LIBRARY_DB_PATH", str(APP_DIR / "library.db")))
MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(page_title="Library Management System", page_icon="📚", layout="wide")


@contextmanager
def db_connection():
    """Open a short-lived SQLite connection and always close it."""
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


def init_db():
    with db_connection() as conn:
        conn.executescript(
            """
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

            CREATE INDEX IF NOT EXISTS idx_loans_active
            ON loans(book_id, return_date);
            CREATE INDEX IF NOT EXISTS idx_loans_due
            ON loans(due_date, return_date);
            """
        )


def get_books(search="", category="All"):
    sql = """
        SELECT b.*,
          b.quantity - (
            SELECT COUNT(*) FROM loans l
            WHERE l.book_id = b.id AND l.return_date IS NULL
          ) AS available,
          (
            SELECT COUNT(*) FROM loans l
            WHERE l.book_id = b.id AND l.return_date IS NULL
          ) AS borrowed
        FROM books b
        WHERE (b.title LIKE ? OR b.author LIKE ? OR COALESCE(b.isbn, '') LIKE ?)
    """
    params = [f"%{search}%", f"%{search}%", f"%{search}%"]
    if category != "All":
        sql += " AND b.category = ?"
        params.append(category)
    sql += " ORDER BY b.title COLLATE NOCASE"
    with db_connection() as conn:
        return conn.execute(sql, params).fetchall()


def get_categories():
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM books ORDER BY category"
        ).fetchall()
    return [row["category"] for row in rows]


def add_book(title, author, isbn, category, quantity):
    isbn = isbn.strip() or None
    with db_connection() as conn:
        conn.execute(
            """INSERT INTO books(title, author, isbn, category, quantity)
               VALUES (?, ?, ?, ?, ?)""",
            (title.strip(), author.strip(), isbn, category.strip() or "General", quantity),
        )


def update_book(book_id, title, author, isbn, category, quantity):
    isbn = isbn.strip() or None
    with db_connection() as conn:
        active = conn.execute(
            "SELECT COUNT(*) FROM loans WHERE book_id=? AND return_date IS NULL",
            (book_id,),
        ).fetchone()[0]
        if quantity < active:
            raise ValueError(
                f"Quantity cannot be lower than the {active} copy/copies currently on loan."
            )
        conn.execute(
            """UPDATE books SET title=?, author=?, isbn=?, category=?, quantity=?
               WHERE id=?""",
            (title.strip(), author.strip(), isbn, category.strip() or "General", quantity, book_id),
        )


def delete_book(book_id):
    with db_connection() as conn:
        active = conn.execute(
            "SELECT COUNT(*) FROM loans WHERE book_id=? AND return_date IS NULL",
