# PerformTrack database schema

## Scope and rollout

The schema targets PostgreSQL and is represented by SQLAlchemy 2.0 models in `backend/app/models/entities.py`. The Alembic revision `20261106_01` creates missing tables without dropping tables or rows; revision `20261108_01` adds Evidence to the existing immutable audit history. Both revisions are applied to the configured local `performtrack_db`. Synthetic baseline records are loaded separately by the explicit generator described in [SYNTHETIC_DATA.md](./SYNTHETIC_DATA.md); they are not part of the migrations.

The initial revision's downgrade intentionally raises an error rather than dropping schema objects or data. Future changes should use reviewed forward migrations.

## Deterministic IDs

All IDs are strings and are the same values to use in PostgreSQL, CSV, JSON, and SQL exports:

| Entity | Format | Allocation |
|---|---|---|
| Employee | `EMP-000001` | Dedicated allocator counter, six digits, starts at 1 |
| Manager | `MGR-000001` | Dedicated allocator counter, six digits, starts at 1 |
| ReviewCycle | `CYCLE-2026-H1` | `format_cycle_id(year, half)` |
| Goal | `GOAL-EMP-000001-001` | `format_goal_id(employee_id, counter)` |
| KeyResult | `KR-GOAL-EMP-000001-001-01` | `format_key_result_id(goal_id, counter)` |
| CheckIn | `CHK-000001` | Dedicated allocator counter, six digits, starts at 1 |
| Competency | `COMP-000001` | Dedicated allocator counter, six digits, starts at 1 |
| Feedback | `FB-000001` | Dedicated allocator counter, six digits, starts at 1 |
| Review | `REV-2026-000001` | `format_review_id(year, counter)` |
| DevelopmentPlan | `DEV-000001` | Dedicated allocator counter, six digits, starts at 1 |

`backend/app/models/ids.py` defines the explicit formats and the fixed `ID_GENERATION_SEED = 20261022`. `DeterministicIdAllocator` uses dedicated, in-memory counters; the same seed and call order reproduce the same IDs. Business IDs are supplied by the allocator, not PostgreSQL sequences. Goal and key-result IDs embed their parent IDs, and database checks validate those embedded IDs against their actual employee/goal foreign keys. Review-cycle IDs are constrained to the selected year and half. IDs cannot be changed after insertion (database trigger).

Goal counters are three digits (001–999) per employee, key-result counters are two digits (01–99) per goal, and other explicit counters are six digits. The primary key prevents duplicates.

## Relationships

- An employee can have one optional reporting manager; a manager profile belongs to exactly one employee and can supervise many employees. The employee/manager foreign keys are deferred to allow a manager's employee record and manager profile to be created in the same transaction.
- A review cycle has many goals, check-ins, feedback entries, reviews, and development plans. A cycle is unique by year and half.
- An employee owns many goals, check-ins, reviews, feedback entries, and development plans. Goals belong to one review cycle and can have many key results.
- Check-ins and key results are many-to-many through `checkin_key_results`.
- Employees and competencies are many-to-many through `employee_competencies` (with effective dates and proficiency). Goals and competencies use `goal_competencies`.
- Feedback and competencies use `feedback_competencies`; reviews and competencies use `review_competencies`.
- Development plans and goals use `development_plan_goals`; development plans and competencies use `development_plan_competencies`.
- Feedback has distinct author and subject employee references. Reviews reference the employee being reviewed, the manager reviewing them, and their cycle.
- Evidence belongs to one employee and exactly one key result, check-in, feedback entry, or review. Each target is a real foreign key.
- Reviews and development plans each have approval rows keyed by the item and approver manager. Pending approvals have no decision time; approved/rejected approvals require one.
- `entity_history` stores insert, update, and delete snapshots for core entities including Evidence, plus inserts, updates, and deletes in the many-to-many bridge tables. Bridge events point to their owning employee/goal/check-in/feedback/review/development plan. It records the string entity ID and type (without a foreign key so deleted records remain auditable), actor, timestamp, action, JSONB before/after snapshots, and a generated UUID event ID. History rows are protected from UPDATE, DELETE, and TRUNCATE through database triggers. Use `set_audit_actor(session, employee_id)` to associate writes with an employee; writes without an actor context are marked `SYSTEM`.

## Constraints and indexes

- Primary keys are `VARCHAR` values; entity-specific `CHECK` constraints enforce the ID shapes. Additional checks tie cycle IDs to year/half, goal IDs to employee IDs, key-result IDs to goal IDs, and review IDs to their year.
- Foreign keys use `ON DELETE RESTRICT`; associations also use composite primary keys to prevent duplicate links. No cascading delete can erase historical records.
- Lifecycle statuses are limited to explicit values per entity. Effective date ranges cannot end before they start.
- Reviews are unique per employee per cycle and ratings are in the 0–5 range. Key-result targets must be positive and progress nonnegative. Feedback cannot target its author.
- Evidence and history each enforce exactly one target. Approval state and decision timestamps must agree.
- Indexes cover employee/status lookups, cycle/status lookups, manager references, due dates, and history type/time searches.
- The initial migration installs triggers that reject primary-key changes, record entity/relationship history, and reject history-row updates/deletes.

## Apply to another database

From `backend/`, after confirming this design and configuring `backend/.env`:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\alembic upgrade head
```

The migration does not create business records. Review the models and this document before applying it to another database. It is already applied to the configured local `performtrack_db`.
