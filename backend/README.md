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
was delivered. SMTP delivery runs after the API response; on a delivery failure
the code is removed and the failure is logged without including the code in
production logs. The user can request another code after the cooldown.

For Mailtrap or another SMTP provider, copy the sandbox credentials from its
SMTP settings into `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD`,
set `SMTP_FROM` to the provider-approved sender, and set `SMTP_TLS` according to
the provider's instructions. Keep credentials in the local `.env` or secret
store; never commit them. Do not use `no-reply@localhost` outside local Mailpit
testing.

## Authentication and email verification

- `POST /auth/signup` creates or updates an unverified account and queues a six-digit email code.
- `POST /auth/verify-email` consumes the code and returns a bearer access token.
- `POST /auth/resend-code` resends a verification code without disclosing whether an account exists.
- `POST /auth/login` requires a verified account.
- `POST /auth/forgot-password` and `POST /auth/reset-password` handle password recovery.
- `GET /auth/me`, `PUT /auth/me`, and `DELETE /auth/me` manage the authenticated account.
- `POST /auth/logout` persistently revokes the current token.

Codes are HMAC-SHA256 hashed in the database, expire after 10 minutes, allow at
most five attempts, and have a 60-second resend cooldown. Existing accounts
created before email verification was enabled can be grandfathered in once,
before enabling the updated signup flow, with:

```sql
UPDATE users SET is_verified = TRUE WHERE is_verified = FALSE;
```

Do not run this statement after accepting new signups, as it would also verify
new accounts that have not confirmed their email.

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
renamed from the sidebar. Follow-up questions are rewritten as standalone
questions using up to the three latest question/answer/code exchanges; this
text-only memory is capped at 1,800 UTF-8 bytes and never includes dataset rows.
If a reference cannot be resolved safely, the assistant asks for clarification.

## Advanced history and sidebar

History APIs require the user's bearer token and only expose their own records.
The startup schema migration adds the analysis title, favorite, and soft-delete
columns and the user/deletion/date index when they are missing.

- `GET /analysis/history?q=&favorite=&limit=20&offset=0` searches question,
  answer, and title with bounded pagination.
- `PATCH /analysis/{id}` updates an analysis title or favorite state.
- `DELETE /analysis/{id}` soft-deletes the analysis; `POST /analysis/{id}/restore`
  restores it within 30 seconds.
- `GET /conversations?q=&favorite=&limit=20&offset=0` searches conversation
  titles and active analysis text, and supports bounded pagination.
- `DELETE /files/{id}?cascade=false` removes an unused dataset; set
  `cascade=true` to also soft-delete analyses that use it.

No additional environment variables are required for history management.

## Analysis exports

Authenticated users can export a saved analysis without rerunning it:

- `GET /analysis/{id}/export?format=pdf` creates a PDF report. For analyses in
  a conversation, the report includes that conversation's saved turns.
- `GET /analysis/{id}/export?format=xlsx` creates an Excel workbook with
  `Résumé` and `Données` sheets and a native chart when the saved chart supports it.

Result tables are stored with the analysis (up to 1,000 rows). Text written to
Excel cells is escaped against formula injection; PDF text is HTML-escaped.
The frontend can also export the displayed chart as PNG directly in the browser.

## Read-only analysis sharing

Authenticated analysis owners can create links with `POST /analysis/{id}/share`
and an `expires_in_days` value of `1`, `7`, or `30`, list active links with
`GET /analysis/{id}/share`, revoke one with
`DELETE /analysis/{id}/share/{share_id}`, or revoke all links with
`DELETE /analysis/{id}/share`. The creation response contains the raw URL-safe
token once; only its SHA-256 hash is persisted.

`GET /public/analysis/{token}` requires no login and returns only the question,
answer, chart configuration, and creation date. Public links are rate-limited,
uncacheable, marked `noindex`, and return the same not-found response when
invalid, expired, or revoked. They are read-only and are not bearer credentials.
There are no additional environment variables for sharing.

## Quotas and administration

`DEFAULT_MONTHLY_QUOTA` sets the monthly analysis allowance for new accounts.
`ANALYSIS_USER_RPM` sets the per-user analysis request limit (default `5`);
`GROQ_GLOBAL_RPM` limits requests sent to Groq across this backend process
(default `20`). When the global limit is reached, analysis requests return
`429` with a `Retry-After` value instead of being queued. These values are in
`backend/.env.example`; set them in the local secret configuration as needed.

The first administrator is bootstrapped without a public API: set
`INITIAL_ADMIN_EMAIL` to the email address of an existing account and restart
the backend. Startup promotes only that matching account. Public signup never
accepts or assigns an administrator role.

- `GET /usage/me` reports the current month's successful analyses, quota,
  token totals, and reset timestamp.
- `GET /admin/users`, `PATCH /admin/users/{id}`, and `GET /admin/stats` require
  the administrator role. The admin page is available at `/admin`.
- Failed server-side analyses are logged for error-rate reporting but do not
  consume monthly quota.

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

## Upload formats

The upload API extracts CSV, XLS/XLSX, PDF, DOC/DOCX, PNG, and JPEG files.
Image and scanned-PDF OCR also require Tesseract OCR with French and English
language data on `PATH`. Reading legacy `.doc` files requires LibreOffice,
antiword, or catdoc; `.docx` files do not need an external converter.
