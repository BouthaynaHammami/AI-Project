# Backend - AI Data Analyst

FastAPI API for the AI Data Analyst application.

## Requirements

- Python 3.11+
- PostgreSQL for production (SQLite can be used for local development)

## Local setup (Windows PowerShell)

From the repository root:

```powershell
cd backend
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `ENV=dev` and a valid `DATABASE_URL` in `backend\.env`. For local development,
the application generates an ephemeral JWT key if `JWT_SECRET_KEY` is empty;
users will need to sign in again after a backend restart. Set a stable,
random `JWT_SECRET_KEY` of at least 32 characters to keep local sessions across
restarts. Never use `ENV=dev` in production.

## Email delivery

The backend `.env` file must have SMTP settings for verification and password
reset messages to be delivered. For local email testing, run Mailpit, then set
these values in `backend\.env`:

```env
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_TLS=false
SMTP_FROM=AI Data Analyst <no-reply@localhost>
```

Open the Mailpit inbox at `http://localhost:8025`. If you do not run Mailpit,
clear `SMTP_HOST` and `SMTP_FROM` in `backend\.env`; verification codes are
then written to the backend terminal only when `ENV=dev`;
the frontend indicates this development mode instead of claiming that an email
was delivered. If SMTP is configured but delivery fails, the API reports the
failure and the user can request another code.

For a real inbox, use an SMTP provider's host, port, sender address, username,
password, and TLS requirements in `backend\.env`. Do not use `no-reply@localhost`
outside local Mailpit testing.

## Run the backend

```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation: `http://localhost:8000/docs`.

## Conversation history

Authenticated conversation routes are available at `/conversations`:

- `POST /conversations` creates a new chat, optionally with owned dataset IDs.
- `GET /conversations` lists the signed-in user's chats.
- `GET /conversations/{id}` returns the full ordered message history.
- `POST /conversations/{id}/messages` analyzes a question in that chat and saves
  both the question and its answer/result.
- `PATCH /conversations/{id}` updates its title, favorite state, or dataset list.
- `DELETE /conversations/{id}` deletes the chat and its associated analyses.

The analysis context is loaded only from earlier analyses in the same
conversation. A chat title is set from its first question and can then be
renamed from the sidebar.

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

## Upload formats

The upload API extracts CSV, XLS/XLSX, PDF, DOC/DOCX, PNG, and JPEG files.
Image and scanned-PDF OCR also require Tesseract OCR with French and English
language data on `PATH`. Reading legacy `.doc` files requires LibreOffice,
antiword, or catdoc; `.docx` files do not need an external converter.
