# Backend - AI Data Analyst

FastAPI API for the AI Data Analyst application.

## Requirements

- Python 3.11
- PostgreSQL for production, or SQLite for local development

## Local setup (Windows PowerShell)

From the repository root:

```powershell
cd "D:\Esprit\5 SAE\IA\AI-Project\backend"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `ENV=dev` and `DATABASE_URL=sqlite:///./database.db` in `backend\.env`.
With no `JWT_SECRET_KEY`, development generates an ephemeral key; sessions expire
when the backend restarts. Production must use a random key of at least 32
characters and must not use `ENV=dev`.

## Email delivery

For local testing, run Mailpit and configure its SMTP endpoint:

```env
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_TLS=false
SMTP_FROM=AI Data Analyst <no-reply@localhost>
```

Open the Mailpit inbox at `http://localhost:8025`. For Mailtrap, use the SMTP
host, username, password, and sender supplied by its inbox, normally port 587
with `SMTP_TLS=true`. If SMTP is not configured, verification codes are written
to application logs only when `ENV=dev`.

## Run the backend

```powershell
cd "D:\Esprit\5 SAE\IA\AI-Project\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation: `http://localhost:8000/docs`.

## Authentication endpoints

- `POST /auth/signup`
- `POST /auth/verify-email`
- `POST /auth/resend-code`
- `POST /auth/login`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET` / `PUT /auth/me`
- `POST /auth/logout`

Codes expire after 10 minutes, allow five attempts, and are stored as HMAC
digests. Rate limits return HTTP 429 with `Retry-After`. Existing accounts
created before email verification can be marked verified after reviewing the
migration with:

```sql
UPDATE users SET is_verified = TRUE WHERE is_verified = FALSE;
```

The application creates the `email_codes` and `revoked_tokens` tables and adds
the authentication columns to existing user tables during startup.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Upload formats

The upload API extracts CSV, XLS/XLSX, PDF, DOC/DOCX, PNG, and JPEG files.
Image and scanned-PDF OCR also require Tesseract OCR with French and English
language data on `PATH`. Reading legacy `.doc` files requires LibreOffice,
antiword, or catdoc; `.docx` files do not require an external converter.

## Security notes

The frontend currently stores bearer tokens in `localStorage`. Any successful
cross-site scripting vulnerability can expose these tokens; use strict output
escaping and a restrictive Content Security Policy, and consider migrating to
httpOnly cookies with CSRF protection for a higher-assurance deployment.
