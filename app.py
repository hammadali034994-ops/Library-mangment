"""
Library Management System
-------------------------
Streamlit UI + SQLite storage + Google Gemini Flash for AI features.

Run locally:  streamlit run app.py
"""

import os
import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.db")
GEMINI_MODEL = "gemini-2.5-flash"  # Gemini Flash model
DEFAULT_LOAN_DAYS = 14

st.set_page_config(page_title="Library Manager", page_icon="📚", layout="wide")


# ----------------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                title         TEXT NOT NULL,
                author        TEXT NOT NULL,
                isbn          TEXT UNIQUE,
                category      TEXT,
                copies_total  INTEGER NOT NULL DEFAULT 1 CHECK (copies_total >= 0)
            );

            CREATE TABLE IF NOT EXISTS members (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT NOT NULL,
                contact  TEXT,
                joined   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS loans (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id      INTEGER NOT NULL REFERENCES books(id),
                member_id    INTEGER NOT NULL REFERENCES members(id),
                issue_date   TEXT NOT NULL,
                due_date     TEXT NOT NULL,
                return_date  TEXT
            );
            """
        )


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with closing(get_conn()) as conn:
        return pd.read_sql_query(sql, conn, params=params)


BOOKS_WITH_AVAILABILITY_SQL = """
    SELECT b.id,
           b.title,
           b.author,
           b.isbn,
           b.category,
           b.copies_total AS total,
           b.copies_total - COUNT(l.id) AS available
    FROM books b
    LEFT JOIN loans l ON l.book_id = b.id AND l.return_date IS NULL
    GROUP BY b.id
    ORDER BY b.title COLLATE NOCASE
"""


def get_books() -> pd.DataFrame:
    return query_df(BOOKS_WITH_AVAILABILITY_SQL)


def get_members() -> pd.DataFrame:
    return query_df(
        "SELECT id, name, contact, joined FROM members ORDER BY name COLLATE NOCASE"
    )


def get_active_loans() -> pd.DataFrame:
    return query_df(
        """
        SELECT l.id AS loan_id,
               b.title,
               m.name AS member,
               l.issue_date,
               l.due_date
        FROM loans l
        JOIN books b   ON b.id = l.book_id
        JOIN members m ON m.id = l.member_id
        WHERE l.return_date IS NULL
        ORDER BY l.due_date
        """
    )


def get_overdue_loans() -> pd.DataFrame:
    df = query_df(
        """
        SELECT l.id AS loan_id,
               b.title,
               m.name AS member,
               m.contact,
               l.issue_date,
               l.due_date
        FROM loans l
        JOIN books b   ON b.id = l.book_id
        JOIN members m ON m.id = l.member_id
        WHERE l.return_date IS NULL AND l.due_date < ?
        ORDER BY l.due_date
        """,
        (date.today().isoformat(),),
    )
    if not df.empty:
        today = pd.Timestamp(date.today())
        df["days_overdue"] = (today - pd.to_datetime(df["due_date"])).dt.days
    return df


def get_loan_history() -> pd.DataFrame:
    return query_df(
        """
        SELECT l.id AS loan_id,
               b.title,
               m.name AS member,
               l.issue_date,
               l.due_date,
               l.return_date
        FROM loans l
        JOIN books b   ON b.id = l.book_id
        JOIN members m ON m.id = l.member_id
        ORDER BY l.id DESC
        """
    )


# ----------------------------------------------------------------------------
# Business logic (each returns (ok: bool, message: str))
# ----------------------------------------------------------------------------
def add_book(title, author, isbn, category, copies):
    title, author = title.strip(), author.strip()
    isbn = isbn.strip() or None
    category = category.strip() or None
    if not title or not author:
        return False, "Title and author are required."
    try:
        with closing(get_conn()) as conn, conn:
            conn.execute(
                "INSERT INTO books (title, author, isbn, category, copies_total) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, author, isbn, category, int(copies)),
            )
        return True, f"Book '{title}' added."
    except sqlite3.IntegrityError:
        return False, "A book with this ISBN already exists."


def delete_book(book_id):
    with closing(get_conn()) as conn, conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM loans WHERE book_id = ?", (book_id,)
        ).fetchone()[0]
        if used:
            return False, "Cannot delete: this book has borrowing records."
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    return True, "Book deleted."


def add_member(name, contact):
    name = name.strip()
    if not name:
        return False, "Member name is required."
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO members (name, contact, joined) VALUES (?, ?, ?)",
            (name, contact.strip() or None, date.today().isoformat()),
        )
    return True, f"Member '{name}' added."


def delete_member(member_id):
    with closing(get_conn()) as conn, conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM loans WHERE member_id = ?", (member_id,)
        ).fetchone()[0]
        if used:
            return False, "Cannot delete: this member has borrowing records."
        conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    return True, "Member deleted."


def issue_book(book_id, member_id, days):
    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            """
            SELECT b.copies_total - COUNT(l.id) AS available
            FROM books b
            LEFT JOIN loans l ON l.book_id = b.id AND l.return_date IS NULL
            WHERE b.id = ?
            GROUP BY b.id
            """,
            (book_id,),
        ).fetchone()
        if row is None:
            return False, "Book not found."
        if row["available"] <= 0:
            return False, "No copies of this book are available."

        already = conn.execute(
            "SELECT COUNT(*) FROM loans "
            "WHERE book_id = ? AND member_id = ? AND return_date IS NULL",
            (book_id, member_id),
        ).fetchone()[0]
        if already:
            return False, "This member already has a copy of this book."

        issued = date.today()
        due = issued + timedelta(days=int(days))
        conn.execute(
            "INSERT INTO loans (book_id, member_id, issue_date, due_date) "
            "VALUES (?, ?, ?, ?)",
            (book_id, member_id, issued.isoformat(), due.isoformat()),
        )
    return True, f"Book issued. Due date: {due.isoformat()}."


def return_book(loan_id):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "UPDATE loans SET return_date = ? WHERE id = ? AND return_date IS NULL",
            (date.today().isoformat(), loan_id),
        )
        if cur.rowcount == 0:
            return False, "Loan not found or already returned."
    return True, "Book returned successfully."


# ----------------------------------------------------------------------------
# Gemini helpers
# ----------------------------------------------------------------------------
def get_api_key() -> str:
    """Sidebar input > Streamlit secrets > environment variable."""
    typed = st.session_state.get("api_key_input", "").strip()
    if typed:
        return typed
    try:
        secret = st.secrets.get("GEMINI_API_KEY", "")
        if secret:
            return str(secret).strip()
    except Exception:
        pass  # no secrets file present
    return os.environ.get("GEMINI_API_KEY", "").strip()


def ask_gemini(prompt: str):
    """Returns (ok, text). Never raises, so the app does not crash."""
    api_key = get_api_key()
    if not api_key:
        return False, "No Gemini API key found. Add it in the sidebar or in secrets."
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = (response.text or "").strip()
        return (True, text) if text else (False, "Gemini returned an empty response.")
    except Exception as exc:  # network error, invalid key, quota, etc.
        return False, f"Gemini request failed: {exc}"


def library_snapshot() -> str:
    """Compact text description of the library for the AI to reason over."""
    books = get_books().head(200)
    active = get_active_loans().head(200)
    overdue = get_overdue_loans().head(100)
    members = get_members()

    parts = [
        f"Today's date: {date.today().isoformat()}",
        f"Total members: {len(members)}",
        "BOOKS (id | title | author | category | available/total):",
    ]
    for r in books.itertuples():
        parts.append(
            f"{r.id} | {r.title} | {r.author} | {r.category or '-'} | {r.available}/{r.total}"
        )
    parts.append("ACTIVE LOANS (title | member | issued | due):")
    for r in active.itertuples():
        parts.append(f"{r.title} | {r.member} | {r.issue_date} | {r.due_date}")
    parts.append("OVERDUE LOANS (title | member | due | days overdue):")
    for r in overdue.itertuples():
        parts.append(f"{r.title} | {r.member} | {r.due_date} | {r.days_overdue}")
    return "\n".join(parts)


# ----------------------------------------------------------------------------
# UI helpers
# ----------------------------------------------------------------------------
def flash(kind: str, message: str) -> None:
    st.session_state["flash"] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("flash", None)
    if item:
        kind, message = item
        (st.success if kind == "success" else st.error)(message)


def result_and_rerun(result) -> None:
    ok, message = result
    flash("success" if ok else "error", message)
    st.rerun()


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
def page_dashboard():
    st.header("📊 Dashboard")
    books = get_books()
    members = get_members()
    active = get_active_loans()
    overdue = get_overdue_loans()

    total_copies = int(books["total"].sum()) if not books.empty else 0
    available = int(books["available"].sum()) if not books.empty else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Book titles", len(books))
    c2.metric("Copies available", f"{available} / {total_copies}")
    c3.metric("Members", len(members))
    c4.metric("Borrowed now", len(active))
    c5.metric("Overdue", len(overdue))

    st.subheader("⚠️ Overdue books")
    if overdue.empty:
        st.info("No overdue books. 🎉")
    else:
        st.dataframe(overdue, hide_index=True)

    st.subheader("📖 Currently borrowed")
    if active.empty:
        st.info("No books are currently borrowed.")
    else:
        st.dataframe(active, hide_index=True)


def page_books():
    st.header("📚 Books")

    with st.expander("➕ Add a new book", expanded=False):
        with st.form("add_book_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            title = c1.text_input("Title *")
            author = c2.text_input("Author *")
            c3, c4, c5 = st.columns(3)
            isbn = c3.text_input("ISBN (optional)")
            category = c4.text_input("Category (optional)")
            copies = c5.number_input("Copies", min_value=1, value=1, step=1)
            if st.form_submit_button("Add book"):
                result_and_rerun(add_book(title, author, isbn, category, copies))

    search = st.text_input("🔍 Search by title, author, ISBN or category")
    books = get_books()
    if search.strip() and not books.empty:
        needle = search.strip().lower()
        mask = (
            books[["title", "author", "isbn", "category"]]
            .fillna("")
            .astype(str)
            .apply(lambda col: col.str.lower().str.contains(needle, regex=False))
            .any(axis=1)
        )
        books = books[mask]

    if books.empty:
        st.info("No books found. Add your first book above.")
    else:
        st.dataframe(books, hide_index=True)

    all_books = get_books()
    if not all_books.empty:
        with st.expander("🗑️ Delete a book"):
            labels = {int(r.id): f"{r.title} — {r.author}" for r in all_books.itertuples()}
            book_id = st.selectbox(
                "Select book", list(labels.keys()), format_func=lambda i: labels[i],
                key="delete_book_select",
            )
            if st.button("Delete book"):
                result_and_rerun(delete_book(book_id))


def page_members():
    st.header("👥 Members")

    with st.expander("➕ Add a new member", expanded=False):
        with st.form("add_member_form", clear_on_submit=True):
            name = st.text_input("Name *")
            contact = st.text_input("Phone / Email (optional)")
            if st.form_submit_button("Add member"):
                result_and_rerun(add_member(name, contact))

    members = get_members()
    if members.empty:
        st.info("No members yet. Add your first member above.")
        return
    st.dataframe(members, hide_index=True)

    with st.expander("🗑️ Delete a member"):
        labels = {int(r.id): r.name for r in members.itertuples()}
        member_id = st.selectbox(
            "Select member", list(labels.keys()), format_func=lambda i: labels[i],
            key="delete_member_select",
        )
        if st.button("Delete member"):
            result_and_rerun(delete_member(member_id))


def page_borrowing():
    st.header("🔄 Issue & Return")
    tab_issue, tab_return, tab_history = st.tabs(["Issue a book", "Return a book", "History"])

    with tab_issue:
        books = get_books()
        members = get_members()
        available_books = books[books["available"] > 0] if not books.empty else books

        if available_books.empty or members.empty:
            st.info("You need at least one member and one available book to issue a book.")
        else:
            book_labels = {
                int(r.id): f"{r.title} — {r.author} ({r.available} available)"
                for r in available_books.itertuples()
            }
            member_labels = {int(r.id): r.name for r in members.itertuples()}
            with st.form("issue_form"):
                book_id = st.selectbox(
                    "Book", list(book_labels.keys()), format_func=lambda i: book_labels[i]
                )
                member_id = st.selectbox(
                    "Member", list(member_labels.keys()), format_func=lambda i: member_labels[i]
                )
                days = st.number_input(
                    "Loan period (days)", min_value=1, max_value=365,
                    value=DEFAULT_LOAN_DAYS, step=1,
                )
                if st.form_submit_button("Issue book"):
                    result_and_rerun(issue_book(book_id, member_id, days))

    with tab_return:
        active = get_active_loans()
        if active.empty:
            st.info("No books are currently borrowed.")
        else:
            labels = {
                int(r.loan_id): f"{r.title} — {r.member} (due {r.due_date})"
                for r in active.itertuples()
            }
            with st.form("return_form"):
                loan_id = st.selectbox(
                    "Borrowed book", list(labels.keys()), format_func=lambda i: labels[i]
                )
                if st.form_submit_button("Mark as returned"):
                    result_and_rerun(return_book(loan_id))

    with tab_history:
        history = get_loan_history()
        if history.empty:
            st.info("No borrowing history yet.")
        else:
            st.dataframe(history, hide_index=True)


def page_ai():
    st.header("🤖 AI Assistant (Gemini Flash)")
    if not get_api_key():
        st.warning("Add your Gemini API key in the sidebar to use the AI features.")

    tab_ask, tab_reco, tab_desc = st.tabs(
        ["Ask about the library", "Recommend books", "Book description"]
    )

    with tab_ask:
        st.caption("Examples: “Which books are overdue?”, “Do we have any science books available?”")
        question = st.text_area("Your question", key="ai_question")
        if st.button("Ask Gemini", key="ask_btn"):
            if not question.strip():
                st.error("Please type a question.")
            else:
                prompt = (
                    "You are a helpful library assistant. Answer ONLY using the library "
                    "data below. If the data does not contain the answer, say so.\n\n"
                    f"{library_snapshot()}\n\nQuestion: {question.strip()}"
                )
                with st.spinner("Thinking..."):
                    ok, text = ask_gemini(prompt)
                (st.markdown if ok else st.error)(text)

    with tab_reco:
        members = get_members()
        if members.empty:
            st.info("Add a member first.")
        else:
            labels = {int(r.id): r.name for r in members.itertuples()}
            member_id = st.selectbox(
                "Member", list(labels.keys()), format_func=lambda i: labels[i], key="reco_member"
            )
            if st.button("Get recommendations", key="reco_btn"):
                history = query_df(
                    "SELECT b.title, b.author, b.category FROM loans l "
                    "JOIN books b ON b.id = l.book_id WHERE l.member_id = ?",
                    (member_id,),
                )
                books = get_books()
                available = books[books["available"] > 0].head(150)
                if available.empty:
                    st.info("No available books to recommend.")
                else:
                    read = (
                        "\n".join(f"- {r.title} by {r.author} ({r.category or '-'})"
                                  for r in history.itertuples())
                        or "- (no borrowing history yet)"
                    )
                    catalog = "\n".join(
                        f"- {r.title} by {r.author} ({r.category or '-'})"
                        for r in available.itertuples()
                    )
                    prompt = (
                        "You are a librarian. Based on the member's borrowing history, "
                        "recommend up to 3 books ONLY from the available catalog and give "
                        "a one-line reason for each.\n\n"
                        f"Borrowing history:\n{read}\n\nAvailable catalog:\n{catalog}"
                    )
                    with st.spinner("Finding recommendations..."):
                        ok, text = ask_gemini(prompt)
                    (st.markdown if ok else st.error)(text)

    with tab_desc:
        c1, c2 = st.columns(2)
        title = c1.text_input("Book title", key="desc_title")
        author = c2.text_input("Author (optional)", key="desc_author")
        if st.button("Generate description & category", key="desc_btn"):
            if not title.strip():
                st.error("Please enter a book title.")
            else:
                prompt = (
                    "Give a short 2-3 sentence description and one suggested library "
                    f"category (e.g. Fiction, Science, History) for the book '{title.strip()}'"
                    f"{' by ' + author.strip() if author.strip() else ''}. "
                    "If you are unsure the book exists, say so."
                )
                with st.spinner("Generating..."):
                    ok, text = ask_gemini(prompt)
                (st.markdown if ok else st.error)(text)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
PAGES = {
    "📊 Dashboard": page_dashboard,
    "📚 Books": page_books,
    "👥 Members": page_members,
    "🔄 Issue & Return": page_borrowing,
    "🤖 AI Assistant": page_ai,
}


def main():
    init_db()

    st.sidebar.title("📚 Library Manager")
    page = st.sidebar.radio("Go to", list(PAGES.keys()), key="nav")

    st.sidebar.divider()
    st.sidebar.text_input(
        "Gemini API key",
        type="password",
        key="api_key_input",
        help="Optional if GEMINI_API_KEY is set in Streamlit secrets or environment.",
    )
    st.sidebar.caption("Get a free key at https://aistudio.google.com/apikey")

    show_flash()
    PAGES[page]()


main()
