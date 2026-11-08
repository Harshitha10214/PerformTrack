# PerformTrack

PerformTrack is a full-stack **Employee Performance and Goal Management System** built using Next.js, FastAPI, SQLAlchemy, and PostgreSQL. It helps organizations manage employee goals, performance check-ins, feedback, reviews, development plans, evidence, and audit history.

## Features

- **Dashboard** – View performance summaries, goal progress, and recent check-ins.
- **Employee Management** – View and manage employee records.
- **Manager Management** – View manager information.
- **Goal Management** – Track goals, key results, and progress.
- **Check-ins** – Record and review employee progress updates.
- **Feedback** – Manage employee feedback and competency information.
- **Performance Reviews** – Manage review cycles, reviews, and approvals.
- **Development Plans** – Track employee development plans and competencies.
- **Evidence Management** – Upload and access supporting performance evidence.
- **Audit History** – View recorded changes to supported entities.
- **Data Exports** – Access prepared CSV, JSON, and SQL exports.

## Technology Stack

### Frontend
- Next.js
- React
- TypeScript
- Tailwind CSS

### Backend
- Python
- FastAPI
- SQLAlchemy
- Alembic

### Database
- PostgreSQL

## Project Structure

```text
PerformTrack/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── generation/
│   │   ├── models/
│   │   ├── routes/
│   │   ├── schemas/
│   │   └── services/
│   ├── generated/
│   │   ├── full/
│   │   └── starter/
│   ├── migrations/
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   └── services/
│   ├── .env.example
│   ├── package.json
│   └── tsconfig.json
│
├── docs/
│   ├── DATABASE_SCHEMA.md
│   ├── DATA_DICTIONARY.md
│   └── SYNTHETIC_DATA.md
│
├── .gitignore
└── README.md
```

## Prerequisites

Install the following before running the application:

- Node.js 18 or later
- npm 9 or later
- Python 3.11 or later
- PostgreSQL 15 or later
- Git

## Installation and Setup

### 1. Clone the repository

```powershell
git clone https://github.com/Harshitha10214/PerformTrack.git
cd PerformTrack
```

### 2. Database Setup

Create a PostgreSQL database named:

```sql
CREATE DATABASE performtrack_db;
```

Make sure PostgreSQL is running and note your local PostgreSQL username and password.

The initial database migration creates the required schema. It does not automatically create business records.

### 3. Backend Setup

Open a terminal in the project root and run:

```powershell
cd backend
```

Create a Python virtual environment:

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\activate
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

Create the backend environment file:

```powershell
Copy-Item .env.example .env
```

Open `backend/.env` and configure your PostgreSQL connection.

Example:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgresql_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=performtrack_db
```

Update the remaining settings if required by your local environment.

Apply database migrations:

```powershell
alembic upgrade head
```

Start the backend:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend URL:

http://localhost:8000

API documentation:

http://localhost:8000/docs

### 4. Frontend Setup

Open a second terminal from the project root:

```powershell
cd frontend
```

Create the frontend environment file:

```powershell
Copy-Item .env.example .env.local
```

Configure the backend API URL in `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

Install dependencies:

```powershell
npm install
```

Start the frontend:

```powershell
npm run dev
```

Frontend URL:

http://localhost:3000

## Environment Variables

### Frontend

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL for the backend API |

### Backend

| Variable | Description |
|---|---|
| `APP_NAME` | Application name |
| `APP_VERSION` | Application version |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_HOST` | PostgreSQL host |
| `POSTGRES_PORT` | PostgreSQL port |
| `POSTGRES_DB` | PostgreSQL database name |
| `BACKEND_CORS_ORIGINS` | Allowed frontend origins |
| `EVIDENCE_STORAGE_DIR` | Directory used to store evidence attachments |

**Important:** Do not commit `.env` or `.env.local` files. They contain local configuration and may contain sensitive credentials. Use the provided `.env.example` files as templates.

## Database Schema and Migrations

The database uses SQLAlchemy models and Alembic migrations.

Documentation:

- [Database Schema](docs/DATABASE_SCHEMA.md)
- [Data Dictionary](docs/DATA_DICTIONARY.md)

Apply migrations from the backend directory:

```powershell
alembic upgrade head
```

The initial migration creates missing schema objects. It does not seed business records or drop existing data. Its downgrade is intentionally disabled to protect existing data.

## Synthetic Dataset

PerformTrack includes deterministic synthetic data for development and testing.

The generated dataset includes employee, manager, goal, key result, check-in, feedback, review, development plan, evidence, and related records.

The full dataset contains approximately 3,000 employees and supporting performance records. A smaller starter dataset is also included.

Documentation:

- [Synthetic Data Documentation](docs/SYNTHETIC_DATA.md)

The documentation covers dataset generation, PostgreSQL loading, export formats, validation, and anomaly ground truth.

## API Health Check

After starting the backend, open:

http://localhost:8000/api/v1/health

The health endpoint checks the database connection using `SELECT 1`.

A successful response reports:

```json
{
  "database": "connected"
}
```

If the database connection fails, the endpoint returns HTTP 503 with a safe error message.

## Data Exports

The Data & Exports page provides access to prepared:

- CSV files
- JSON files
- SQL files

The API endpoints are:

```text
GET /api/v1/data-exports
GET /api/v1/data-exports/{format}/{filename}
```

The export files are served from:

```text
backend/generated/full/
```

The status endpoint validates exported row counts against the generated validation report and provides file checksums.

Downloads also include supporting documentation such as the README, database schema, data dictionary, generation summary, and validation report.

Exports are served as prepared files. Downloading them does not regenerate the dataset or modify PostgreSQL records.

## Evidence Management

Evidence attachments are uploaded through the backend API.

Supported endpoints include:

```text
GET  /api/v1/evidence
GET  /api/v1/evidence/{id}
POST /api/v1/evidence
GET  /api/v1/evidence/{id}/file
```

Uploaded files are stored outside the frontend public directory.

Supported file types:

- PDF
- UTF-8 text
- PNG
- JPEG

Maximum upload size: 10 MB.

Apply database migrations to enable Evidence entries in the existing audit history.

## Audit History

Audit history is available through:

```text
GET /api/v1/audit-history
GET /api/v1/audit-history/{event_id}
```

The list endpoint supports filtering by:

- Entity type
- Entity ID
- Operation
- Inclusive UTC date range
- Pagination

The audit history provides read-only access to recorded events.

## Testing and Verification

### Backend Tests

From the backend directory, activate the virtual environment and run:

```powershell
python -m pytest
```

The project backend test suite was verified with **77 passing tests**.

### Frontend TypeScript Validation

From the frontend directory:

```powershell
npx tsc --noEmit
```

### Frontend Production Build

```powershell
npm run build
```

The TypeScript validation and production build completed successfully during project verification.

### Manual Verification

Verify the application using:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

## Known Limitations

- Authentication and identity-backed authorization are not implemented.
- API actor IDs are not verified user identities until authentication is implemented.
- Audit history records supported application events; historical records may not have corresponding audit events.
- The initial database migration does not automatically populate business records.
- The Data & Exports page serves prepared files and does not regenerate or modify database records.

## License

This repository was created as a candidate project submission. No separate open-source license has been specified.
