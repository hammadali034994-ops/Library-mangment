# Library Management System

A small library-management web app built with **Python, Streamlit, SQLite, and Google Gemini 2.5 Flash**.

## Features

- Dashboard with total, available, borrowed, and overdue copy counts
- Add, search, filter, edit, and delete books
- Issue books to borrowers with issue and due dates
- Record returns and automatically recalculate availability
- View active loans and complete borrowing history
- Flag overdue loans
- Optional Gemini AI helper for book descriptions, category suggestions, and library questions
- SQLite database with foreign keys, indexes, and transaction-safe issue operations

## Project files

```text
library_management_system/
├── app.py
├── README.md
└── requirements.txt
```

The database file (`library.db`) is created automatically the first time the app runs. It is intentionally not included in Git.

## 1. Requirements

- Python 3.10 or newer (Python 3.11 or 3.12 recommended)
- Git (for GitHub)
- A Google Gemini API key (only needed for the AI page)

Create a key in [Google AI Studio](https://aistudio.google.com/app/apikey).

## 2. Run locally

Open a terminal in this project folder.

### Windows (PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Configure the Gemini API key (optional)

The app works for all book and borrowing operations without an API key. The Gemini AI page requires one.

For local use, create a folder named `.streamlit`, then create `.streamlit/secrets.toml` inside it:

```toml
GEMINI_API_KEY = "paste-your-google-gemini-api-key-here"
```

Alternatively, set an environment variable named `GEMINI_API_KEY`.

**Never commit your real API key to GitHub.** Do not share it in screenshots, messages, or source code.

### Start the app

```bash
streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`.

## 3. Push the project to GitHub

1. Sign in to [GitHub](https://github.com/) and create a new empty repository, for example `library-management-system`. Do not initialize it with a README if you already have this project locally.
2. Open a terminal in the folder containing `app.py`.
3. Run:

```bash
git init
git add app.py README.md requirements.txt
git commit -m "Initial library management system"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/library-management-system.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username. Git may ask you to authenticate through your browser.

### Recommended `.gitignore`

Create a `.gitignore` file before `git add` if you can. Add:

```gitignore
.venv/
__pycache__/
*.py[cod]
.streamlit/secrets.toml
library.db
```

This prevents your local virtual environment, secret key, and local database from being uploaded. The `.gitignore` is an additional recommended file; the application itself is provided in the three requested files.

## 4. Deploy on Streamlit Community Cloud

1. Push the project to GitHub using the steps above.
2. Visit [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with GitHub.
3. Select **Create app**.
4. Choose your repository, branch `main`, and main file path `app.py`.
5. Open **Advanced settings** before deploying.
6. Under **Secrets**, enter:

```toml
GEMINI_API_KEY = "your-real-gemini-api-key"
```

7. Select a supported Python version (3.11 or 3.12 is a good choice), save, and deploy.
8. Wait for the build to finish. Streamlit will provide a public app URL.

Do not put the API key in `app.py`, README, or GitHub. Configure it in Streamlit's Secrets settings.

## 5. Important database and deployment note

This starter app stores data in a SQLite file named `library.db`. That is convenient for local use and testing. **A local SQLite file on Streamlit Community Cloud is not guaranteed to be durable across app restarts, redeployments, or infrastructure changes.** Do not use this default storage setup as the only copy of important real library records.

Before using it for a real library or multiple staff members, move the database to persistent hosted storage (for example, a managed PostgreSQL database) and configure regular backups. Keep a separate backup of your local `library.db` file. Do not upload a database containing borrowers' personal information to a public GitHub repository.

The app has no user login or staff roles. Deploy it privately or add authentication before exposing real borrower information publicly.

## 6. Troubleshooting

- **`streamlit` is not recognized:** activate the virtual environment and run `python -m streamlit run app.py`.
- **Gemini key missing:** check the spelling `GEMINI_API_KEY` in `.streamlit/secrets.toml` locally or Streamlit Cloud Secrets.
- **Gemini request error:** check that the key is valid, the Gemini API is enabled for its Google project, and the account has available quota.
- **App cannot find a book:** clear the search text and set the category filter to `All`.
- **SQLite file location:** by default, `library.db` is created beside `app.py`. Set `LIBRARY_DB_PATH` to change the path.

## 7. How availability works

A book's available-copy count is calculated as:

`available copies = total copies - active (not yet returned) loans`

The app does not manually overwrite availability when issuing or returning a book. It records each loan and calculates availability from the transaction history, reducing the chance of inconsistent counts.
