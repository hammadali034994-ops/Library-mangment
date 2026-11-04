# 📚 Library Management System

A simple web app to manage books, members and borrowing, with AI features
powered by **Google Gemini Flash**. Built with **Streamlit** and **SQLite**.

## Features

- **Dashboard** – total titles, available copies, members, borrowed and overdue books
- **Books** – add, search and delete books (supports multiple copies per title)
- **Members** – add and delete members
- **Issue & Return** – issue books with a due date, return them, view full history
- **Automatic availability** – availability is calculated from the loan records, so counts never go out of sync
- **AI Assistant (Gemini Flash)**
  - Ask questions about your library in plain English
  - Get personalised book recommendations for a member
  - Generate a short description and category for a book

## Project files

| File | Purpose |
|------|---------|
| `app.py` | The complete application |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

## Run locally

1. Install Python 3.9 or newer.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Get a free Gemini API key at <https://aistudio.google.com/apikey>.
4. Provide the key in **one** of these ways (the app checks them in this order):
   - Paste it into the **Gemini API key** box in the app sidebar, or
   - Create `.streamlit/secrets.toml` containing:
     ```toml
     GEMINI_API_KEY = "your-key-here"
     ```
   - Or set an environment variable `GEMINI_API_KEY`.
5. Start the app:
   ```bash
   streamlit run app.py
   ```
   It opens at <http://localhost:8501>.

The app works without an API key; only the AI Assistant page needs one.

## Data storage

Data is stored in a local SQLite file, `library.db`, created automatically on
first run. **Back it up regularly.**

> ⚠️ On Streamlit Community Cloud the file system is temporary: data can be
> reset when the app restarts or redeploys. For permanent online data, connect
> an external database (e.g. Supabase/PostgreSQL, Google Sheets) or deploy on a
> server/VPS where `library.db` persists.

## Deploy

See the step-by-step guide for pushing to GitHub and deploying on
Streamlit Community Cloud (<https://share.streamlit.io>). Remember to put
`GEMINI_API_KEY` in the app's **Secrets** settings, never in your code.

## Security

- Never commit your API key or `.streamlit/secrets.toml` to GitHub.
- Add a `.gitignore` containing `library.db`, `.streamlit/secrets.toml` and `__pycache__/`.
