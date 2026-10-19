# AI Data Analyst - AI Testing Plan

## Testing strategy

The project is divided into five modules. Three testing tools are used:

- **pytest + HTTPX** for FastAPI API and service tests.
- **Vitest + React Testing Library** for React component and service tests.
- **Playwright** for complete browser-to-API end-to-end tests.

Never use real credentials, API keys, email servers, or production data in tests. Use isolated test databases, deterministic fixtures, and mocked external AI/email services.

---

## Module 1 - Authentication and accounts

**Functionality:** User signup, email verification, login, JWT authorization, logout, password reset, profile updates, and account deletion.

**Test:** Valid and invalid credentials, duplicate accounts, weak passwords, expired/reused codes, token expiration and revocation, protected routes, user isolation, rate limits, and sensitive-data exposure.

**Tool and configuration:** `pytest + HTTPX`. Reuse the backend fixtures, override the database dependency with an isolated test database, and mock email delivery. Run:

```powershell
cd backend
python -m pytest tests -q
```

**Copilot prompt:**

```text
Act as a senior FastAPI security QA engineer. Test Module 1 of this AI Data Analyst project using pytest and HTTPX. Inspect the existing fixtures and tests first, then add tests under backend/tests without changing production behavior.

Cover signup, duplicate email rejection, email validation, password-strength and bcrypt-length validation, password hashing, email verification with valid/invalid/expired/reused codes, resend-code behavior, login failures and success, JWT expiration and revocation, /auth/me authorization, logout, forgot-password and reset-password flows, profile updates, account deletion, rate limiting, and authorization isolation between two users.

Use an isolated test database and mock all email delivery. Never read backend/.env, use real credentials, call real email/AI services, or expose tokens, hashes, codes, or secrets. Assert status codes, response bodies, database state, and security boundaries. Run the focused tests and report the command, test count, failures, and uncovered behavior.
```

---

## Module 2 - File ingestion, profiling, and privacy

**Functionality:** Upload and parse CSV, XLS/XLSX, PDF, DOC/DOCX, PNG, and JPEG files; preview data; profile columns; detect PII; apply exclude/mask/allow preferences; list and delete datasets.

**Test:** Supported and unsupported formats, empty files, malformed files, multiple uploads, extraction accuracy, previews, row/column counts, missing values, duplicates, dates, statistics, PII detection and masking, ownership, rollback, and safe file deletion.

**Tool and configuration:** `pytest`. Use temporary files and in-memory uploads. Mock OCR, optional converters, and external services. Run:

```powershell
cd backend
python -m pytest tests -q
```

**Copilot prompt:**

```text
Act as a senior data-processing QA engineer. Test Module 2 of this FastAPI AI Data Analyst project with pytest. Inspect existing tests and fixtures before adding focused tests under backend/tests.

Test valid CSV, XLS, XLSX, PDF, DOCX, PNG, and JPEG uploads where dependencies are available; reject unsupported, empty, missing-name, and malformed files. Verify row counts, column counts, previews, JSON-safe pandas/NumPy values, document page counts, and transaction rollback.

Test profiling for numeric, text, categorical, boolean, and date columns, including missing values, percentages, duplicates, statistics, date ranges, and quality alerts. Test PII detection and exclude/mask/allow preferences, proving sensitive values are not passed to AI input. Test dataset ownership, unauthorized preview/deletion, cascade rules, upload-directory path validation, and physical file cleanup.

Use temporary files, deterministic data, an isolated database, and mocks for OCR/converters. Never read backend/.env or use real user data. Preserve production behavior. Run the focused and full backend suites and report test count, skipped environment-dependent tests, and defects.
```

---

## Module 3 - AI analysis and conversations

**Functionality:** Ask questions about one or more datasets, generate AI answers and charts, execute generated analysis code, suggest questions, maintain conversations, enforce quotas, and save analysis history.

**Test:** Dataset ownership, valid and invalid questions, AI prompts and context, provider failures, generated-code safety, retry behavior, result/chart parsing, suggestions, conversation history, quota handling, persistence, and rollback.

**Tool and configuration:** `pytest`. Mock the Groq/LLM client and use deterministic pandas DataFrames. Run:

```powershell
cd backend
python -m pytest tests -q
```

**Copilot prompt:**

```text
Act as a senior AI-platform QA engineer. Test Module 3 of this FastAPI AI Data Analyst project using pytest. Read the existing AI, analysis, suggestion, and conversation tests first and extend their fixtures and conventions.

Test analysis requests with one and multiple owned datasets, invalid or empty questions, deleted or foreign datasets, quota limits, usage events, and database rollback. Mock the external Groq/LLM provider and verify dataset context, bounded conversation history, PII filtering, malformed responses, and provider failures.

Treat generated Python as untrusted input. Test valid pandas analysis, scalar/table/text/chart results, syntax and runtime retry paths, unsafe imports, filesystem/network/subprocess access, unsafe builtins, infinite-loop limits, JSON serialization, and result-size limits. Test chart validation and suggestion generation, sanitization, categories, duplicates, caching, and provider failures.

Test conversation creation, ownership validation, listing, search, favorites, ordered messages, legacy analysis history, adding messages, renaming, dataset updates, deletion, and cross-user access. Never call a real AI API, read backend/.env, or use secrets. Assert API schemas, database invariants, quota behavior, and failure cleanup. Run focused tests then all backend tests and report results.
```

---

## Module 4 - React interface

**Functionality:** Authentication screens, file selection, analysis dashboard, charts, data preview, chat, history/search/favorites, settings, and admin usage screens.

**Test:** User-visible validation, loading/error states, callbacks, rendering, keyboard interactions, accessibility, service requests, token persistence, and null/empty API data.

**Tool and configuration:** `Vitest + React Testing Library`. Mock API/service modules and do not call the backend. The frontend already defines the test script in `frontend/package.json`. Run:

```powershell
cd frontend
npm run test
npm run build
```

**Copilot prompt:**

```text
Act as a senior React QA engineer. Test Module 4 of this Vite React AI Data Analyst project with Vitest and React Testing Library. Inspect the existing frontend test and configuration first, then add focused tests without changing behavior merely to satisfy tests.

Cover login/signup validation, password visibility, verification-code entry and paste, resend cooldown, password reset, loading states, and API errors. Test CSV/XLSX selection, unsupported-file errors, disabled submit state, selected filename, upload callback, and upload failures.

Test the analysis dashboard metrics, dataset names, chart rendering, malformed chart JSON, numeric fallback chart, document suggestions, chat messages, empty states, and analyzing state. Test history loading, debounced search, favorites, rename with Enter, cancel with Escape, deletion/undo, selection, retry errors, settings updates, logout, account deletion, and admin-only content.

Mock API/service calls and assert HTTP method, URL, query, payload, FormData, token persistence, and error propagation. Prefer roles, labels, accessible names, and user-visible behavior. Test keyboard access and null/empty API responses. Run npm run test and npm run build; report test count, failures, and accessibility defects.
```

---

## Module 5 - Analysis lifecycle, export, and sharing

**Functionality:** Analysis history lifecycle, rename/favorite, feedback, soft delete/restore, XLSX/PDF export, share-link creation/revocation/expiration, and public shared analysis pages.

**Test:** Complete authenticated and public user journeys, downloads, permissions, expired/revoked links, response headers, visible errors, and refresh/direct-navigation behavior.

**Tool and configuration:** `Playwright`. The Playwright configuration starts the frontend and a dedicated backend backed by a temporary SQLite database, then seeds synthetic test accounts, an analysis, and a public share link. The temporary database is removed when the test server exits.

**Copilot prompt:**

```text
Act as a senior end-to-end QA engineer. Test Module 5 of this AI Data Analyst project with Playwright against the running FastAPI backend and React frontend. Inspect routes and existing conventions first.

Create isolated tests for authenticated history search, favorites, rename, opening an analysis, delete/restore, positive and negative feedback, feedback updates/deletion, XLSX and PDF downloads, safe filenames, invalid formats, and unauthorized access.

Test share-link creation for every supported expiration period, public viewing without authentication, displayed question/answer/chart/date, view counts, single-link and all-link revocation, expired links, deleted-analysis invalidation, noindex/no-store response headers, direct public URL navigation, refresh, loading states, and visible API errors.

Do not mock the application API for end-to-end journeys; mock only external services such as the AI provider or email provider. Use isolated accounts and deterministic seed data. Prefer accessible selectors, capture downloads with Playwright, and save traces/screenshots only for failures. Run headlessly and report setup commands, browser version, test count, failures, and defects.

### Module 5 execution

From `frontend`, install the browser once, then run the suite:

```powershell
npx playwright install chromium
<<<<<<< HEAD
$env:E2E_USER_EMAIL = "..."
$env:E2E_USER_PASSWORD = "..."
$env:E2E_ANALYSIS_ID = "..."
npm run test:e2e -- --workers=1
```

`E2E_API_URL` and `E2E_FRONTEND_URL` can override the default endpoints. The public-sharing browser test creates its own temporary share token, so `E2E_SHARE_TOKEN` is not required. The suite does not mock application API calls; when fixture variables are absent, tests are reported as skipped rather than contacting a real account.

---

## Playwright commands - simple guide

Run these commands from `frontend`. Keep the backend running in another terminal.

### 1. Start the application

Backend example:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8090
```

Frontend:

```powershell
cd frontend
$env:VITE_API_URL = "http://127.0.0.1:8090"
npx vite --host 127.0.0.1
```

The backend serves the API on port `8090`; the frontend serves the website on port `5173`.

### 2. Install Playwright Chromium once

```powershell
cd frontend
npx playwright install chromium
```

Downloads the browser used by the tests.

### 3. Run login only

```powershell
cd frontend
$env:E2E_FRONTEND_URL = "http://localhost:5173"
$env:E2E_USER_EMAIL = "your-test-email@example.com"
$env:E2E_USER_PASSWORD = "your-test-password"
npx playwright test e2e/auth.spec.ts --project=chromium
```

Opens the login page, enters the credentials, submits the form, and checks that the authenticated dashboard appears. This test does not need an analysis ID or share token.

### 4. Run one Module 5 test

Set all fixture values first:

```powershell
$env:E2E_API_URL = "http://127.0.0.1:8090"
$env:E2E_USER_EMAIL = "your-test-email@example.com"
$env:E2E_USER_PASSWORD = "your-test-password"
$env:E2E_ANALYSIS_ID = "123"
```

Run a selected test with `-g`:

```powershell
npx playwright test e2e/module5.spec.ts -g "history search"
npx playwright test e2e/module5.spec.ts -g "exports XLSX"
npx playwright test e2e/module5.spec.ts -g "feedback can be created"
npx playwright test e2e/module5.spec.ts -g "another authenticated user"
npx playwright test e2e/module5.spec.ts -g "expiration period"
npx playwright test e2e/module5.spec.ts -g "public URL works"
npx playwright test e2e/module5.spec.ts -g "expired, invalid, or revoked"
```

These tests respectively check history changes, XLSX/PDF downloads, feedback, user isolation, share-link expiration and revocation, public sharing, and unavailable links. The public-sharing test creates its own share token.

### 5. Run all Playwright tests

```powershell
npm run test:e2e
```

Runs the login test and all Module 5 tests sequentially. Tests needing missing fixture values are skipped.

### 6. Useful options

```powershell
npx playwright test e2e/auth.spec.ts --project=chromium --headed
npx playwright test e2e/auth.spec.ts --project=chromium --debug
npx playwright show-report
=======
npm run test:e2e
```

To open Playwright's interactive runner, use `npm run test:e2e:ui`. The suite uses dedicated local ports `18765` and `18766`; it refuses to reuse an existing service and never connects to the regular backend on port `8000`. It does not mock application API calls. The test database and synthetic data are isolated from application data and removed after the run.
>>>>>>> 353023a (Fix profile updates and configure isolated E2E tests)
```

`--headed` shows the browser, `--debug` pauses for investigation, and `show-report` opens the latest HTML report. Screenshots and traces are saved automatically when a test fails.

---

## Suggested execution order

1. Module 1 - Authentication and accounts.
2. Module 2 - File ingestion, profiling, and privacy.
3. Module 3 - AI analysis and conversations.
4. Module 4 - React interface.
5. Module 5 - Analysis lifecycle, export, and sharing.
