# PerformTrack

PerformTrack is a full-stack employee performance and goal management system built with a Next.js frontend and FastAPI backend.

## Project structure

- `frontend/` – React + Next.js application
- `backend/` – FastAPI application with SQLAlchemy and PostgreSQL configuration

## Prerequisites

- Node.js 18+
- npm 9+
- Python 3.11+
- PostgreSQL 15+

## Frontend setup

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

The frontend runs on http://localhost:3000 by default.

## Backend setup

The database `performtrack_db` must already exist; this application does not create business tables.

```bash
cd backend
copy .env.example .env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Before starting the backend, edit `backend/.env` and set `POSTGRES_PASSWORD` to the password for your local PostgreSQL `postgres` user. Do not commit this file.

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend runs on http://localhost:8000 by default.

## Environment variables

Frontend:

- `NEXT_PUBLIC_API_URL` – base URL for the backend API

Backend:

- `APP_NAME`
- `APP_VERSION`
- `POSTGRES_USER` (defaults to `postgres`)
- `POSTGRES_PASSWORD` (set locally; never commit it)
- `POSTGRES_HOST` (defaults to `localhost`)
- `POSTGRES_PORT` (defaults to `5432`)
- `POSTGRES_DB` (defaults to `performtrack_db`)
- `BACKEND_CORS_ORIGINS`
- `EVIDENCE_STORAGE_DIR` (defaults to `backend/storage/evidence`, outside the frontend public directory)

## Health check

- Frontend: http://localhost:3000
- Backend health endpoint: http://localhost:8000/api/v1/health. It runs `SELECT 1` against PostgreSQL and reports `database: "connected"` on success; a failed connection returns HTTP 503 with a safe error message.

## Database schema and migrations

The SQLAlchemy models, schema relationships, constraints, and data dictionary are documented in [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) and [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md). After reviewing those documents and the initial migration, apply it from `backend/` with:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\alembic upgrade head
```

The initial migration creates missing schema objects only; it does not seed records or drop existing data. Its downgrade is intentionally disabled to protect data.

## Notes

The initial database migration does not create business records. The
deterministic starter data generator, PostgreSQL loading instructions, export
formats, and isolated anomaly ground truth are documented in
[docs/SYNTHETIC_DATA.md](docs/SYNTHETIC_DATA.md).

Evidence attachments are uploaded through the API routes documented by FastAPI
(`GET /api/v1/evidence`,
`GET /api/v1/evidence/{id}`, `POST /api/v1/evidence`, and
`GET /api/v1/evidence/{id}/file`). Uploads are stored outside the frontend and
limited to 10 MB PDF, UTF-8 text, PNG, or JPEG files. Apply migrations with
`alembic upgrade head` to enable Evidence entries in the existing audit history.
Authentication is not implemented; these endpoints do not restrict access by
user identity.

Audit history is available read-only through `GET /api/v1/audit-history` and
`GET /api/v1/audit-history/{event_id}`. The list supports entity type, entity
ID, operation, inclusive UTC date range, and pagination filters. Actor IDs are
not verified identities until authentication is implemented.

The Data & Exports page serves the prepared CSV, JSON, and SQL files from
`backend/generated/full/` through `GET /api/v1/data-exports` and
`GET /api/v1/data-exports/{format}/{filename}`. The status endpoint validates
the exported row counts against the generated validation report and returns
file checksums. Downloads also include the README, database schema, data
dictionary, generation summary, and validation report; exports are served as
prepared and do not regenerate or change PostgreSQL records.
