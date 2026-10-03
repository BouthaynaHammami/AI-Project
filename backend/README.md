# Backend - AI Data Analyst

This is the FastAPI backend for the AI Data Analyst project.

## Project structure

```text
backend/
├── app/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── uploads/
├── .env
├── requirements.txt
├── README.md
└── uvicorn
```

## Requirements

- Python 3.11+
- PostgreSQL installed and running
- Virtual environment created at:

```text
D:\Esprit\5 SAE\IA\AI-Project\.env
```

## Create and activate the virtual environment

From the project root:

```powershell
cd "D:\Esprit\5 SAE\IA\AI-Project"
.\.env\Scripts\Activate.ps1
```

## Install dependencies

```powershell
cd "D:\Esprit\5 SAE\IA\AI-Project\backend"
python -m pip install -r requirements.txt
```

## Configure environment

Check the `.env` file in the backend folder and make sure it contains the PostgreSQL database URL:

```env
DATABASE_URL=postgresql+psycopg2://postgres:123@localhost:5432/ai_data_analyst
JWT_SECRET_KEY=your_secret_key
FRONTEND_ORIGIN=http://localhost:5173
```

## Start the backend

```powershell
cd "D:\Esprit\5 SAE\IA\AI-Project\backend"
& "D:\Esprit\5 SAE\IA\AI-Project\.env\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Open API docs

After starting the backend, open:

```text
http://localhost:8000/docs
```

## Main endpoints

### Authentication

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### Datasets

- `GET /datasets`
- `POST /datasets`

### Analyses

- `GET /analyses`
- `POST /analyses`

## Notes

- The backend creates database tables automatically at startup.
- The project uses PostgreSQL and SQLAlchemy.
- JWT authentication is enabled for protected routes.

## Troubleshooting

### App does not start

- Confirm the virtual environment is active.
- Confirm PostgreSQL is running.
- Check the `.env` file for a valid `DATABASE_URL`.
- Reinstall the dependencies if needed.

### Supported upload formats

The upload API extracts data from CSV, XLS/XLSX, PDF, DOC/DOCX, PNG, and JPEG files. Install Python dependencies with `python -m pip install -r requirements.txt`. Image OCR and scanned-PDF OCR also require Tesseract OCR with French and English language data available on `PATH`. Reading legacy `.doc` files requires LibreOffice, antiword, or catdoc; `.docx` files do not need an external converter.
