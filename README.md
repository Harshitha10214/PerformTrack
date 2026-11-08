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
│   │  
