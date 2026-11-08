# Technical Decisions and Design Rationale

## 1. Project Architecture

PerformTrack uses a separate frontend and backend architecture.

- **Frontend:** Next.js, React, TypeScript, and Tailwind CSS.
- **Backend:** FastAPI and Python.
- **Database:** PostgreSQL with SQLAlchemy.
- **Migrations:** Alembic.

**Reasoning:** Separating the frontend and backend makes the application easier to maintain, test, and extend. The frontend communicates with the backend through API endpoints.

## 2. Database Design

PostgreSQL was selected as the relational database.

SQLAlchemy models represent the main entities, including employees, managers, goals, key results, check-ins, feedback, reviews, development plans, and evidence.

Database relationships and constraints help maintain consistency between related records.

Alembic is used to manage database schema changes through migrations.

## 3. Goal Progress Calculation

Goal progress is derived from the associated key results rather than maintained as an unrelated independent value.

**Reasoning:** This keeps goal progress connected to measurable outcomes and reduces inconsistencies between goals and their key results.

## 4. Synthetic Data Generation

The project includes deterministic synthetic datasets for development, testing, and demonstration.

The generated data includes employee performance records and supporting relationships.

A fixed seed is used to support reproducibility. Validation reports and separate anomaly ground truth are included to help verify the generated dataset.

**Trade-off:** Synthetic data provides realistic development scenarios without requiring actual employee information. However, it does not represent real organizational performance.

## 5. API Design

FastAPI provides separate route modules for different application areas.

Request and response schemas are used to validate and structure API data.

The frontend uses a centralized API service to communicate with the backend.

**Reasoning:** This avoids scattering API configuration and request logic throughout the frontend.

## 6. Audit History

Audit history records supported application changes and provides filtering and pagination.

The history is exposed through read-only API endpoints.

**Limitation:** Actor IDs are not verified user identities because authentication has not been implemented.

## 7. Evidence Storage

Evidence attachments are stored outside the frontend public directory.

Supported formats include PDF, UTF-8 text, PNG, and JPEG, with a maximum upload size of 10 MB.

**Reasoning:** Keeping uploaded files outside the public frontend directory avoids exposing them as ordinary static assets.

## 8. Data Export Design

Prepared CSV, JSON, and SQL files are served through dedicated API endpoints.

Export status checks compare row counts with the generated validation report and provide file checksums.

**Trade-off:** Serving prepared exports provides predictable downloads without regenerating data or modifying database records during export requests.

## 9. Testing Strategy

The project includes backend automated tests covering API behaviour, database operations, validation, goal progress, audit history, and data generation.

Frontend validation includes TypeScript checking and a production build.

Manual verification was also performed to check application routes, API integration, and database connectivity.

## 10. Known Limitations and Future Considerations

- Authentication and identity-backed authorization are not implemented.
- Actor IDs are not verified against authenticated users.
- Historical records may not have corresponding audit events.
- Initial database migrations create the schema but do not automatically populate business records.
- The application uses synthetic data for development and demonstration.

These limitations are documented so that the current implementation and its boundaries are clear.
