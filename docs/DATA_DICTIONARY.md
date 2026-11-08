# PerformTrack data dictionary

All tables use SQLAlchemy 2.0 mappings in `backend/app/models/entities.py`. Primary and foreign keys use the exact string IDs described below. Core entities have timezone-aware `created_at` and `updated_at` timestamps. Unless noted, foreign keys restrict deletion to preserve references and history.

## Core entities

| Entity / table | Primary key | Main columns | Relationships / rules |
|---|---|---|---|
| Employee / `employees` | `id`: `EMP-000001` | `manager_id`, `email`, `first_name`, `last_name`, `job_title`, `department`, `hire_date`, `effective_from`, `effective_to`, `status` | Unique email; optional reporting manager; owns goals, check-ins, feedback, reviews, development plans, and competency assignments. |
| Manager / `managers` | `id`: `MGR-000001` | `employee_id`, `effective_from`, `effective_to`, `status` | Unique employee profile; one employee can report to a manager, which can supervise many employees. |
| ReviewCycle / `review_cycles` | `id`: `CYCLE-YYYY-H1` or `CYCLE-YYYY-H2` | `year`, `half`, `name`, `starts_on`, `ends_on`, `status` | Unique `(year, half)`; cycle ID must agree with those values. Owns cycle-scoped goals, check-ins, feedback, reviews, and plans. |
| Goal / `goals` | `id`: `GOAL-EMP-000001-001` | `employee_id`, `review_cycle_id`, `owner_manager_id`, `title`, `description`, `effective_from`, `effective_to`, `due_date`, `status` | Goal ID embeds its employee ID; belongs to one employee and cycle; has many key results; many-to-many with competencies and development plans. |
| KeyResult / `key_results` | `id`: `KR-GOAL-EMP-000001-001-01` | `goal_id`, `title`, `description`, `unit`, `target_value`, nullable `current_value`, nullable `weight`, `effective_from`, `effective_to`, `due_date`, `status` | Goal ID embedded in key-result ID must match its foreign key. Target is positive; actual progress is nonnegative; optional weights are 0–100 and, when used, must total 100 for the goal calculation. |
| CheckIn / `checkins` | `id`: `CHK-000001` | `employee_id`, `manager_id`, `review_cycle_id`, `checkin_date`, `notes`, `status` | Belongs to an employee, optionally a manager and cycle; many-to-many with key results. |
| Competency / `competencies` | `id`: `COMP-000001` | `name`, `category`, `description`, `effective_from`, `effective_to`, `status` | Unique name; many-to-many with employees, goals, feedback, reviews, and development plans. |
| Feedback / `feedback` | `id`: `FB-000001` | `author_employee_id`, `subject_employee_id`, `review_cycle_id`, `content`, `visibility`, `status` | Author and subject are distinct employees; optional review cycle; many-to-many with competencies. |
| Review / `reviews` | `id`: `REV-YYYY-000001` | `year`, `employee_id`, `reviewer_manager_id`, `review_cycle_id`, `summary`, `rating`, `effective_from`, `effective_to`, `status` | Unique employee/cycle; ID year matches `year`; optional 0–5 rating; many-to-many with competencies; has approvals. |
| DevelopmentPlan / `development_plans` | `id`: `DEV-000001` | `employee_id`, `owner_manager_id`, `review_cycle_id`, `title`, `description`, `effective_from`, `effective_to`, `status` | Belongs to an employee and manager, optionally a cycle; many-to-many with same-employee goals and competencies; has approvals. API-created plans start as drafts with a pending owner-manager approval; approval activates the plan and rejection cancels it. Active plans can transition to completed or cancelled; completed and cancelled plans are terminal. Approval manager IDs are validated against the plan owner but not authenticated. |

## Supporting tables

| Table | Key columns | Purpose / constraints |
|---|---|---|
| `employee_competencies` | `(employee_id, competency_id)` | Employee competency assignment with effective dates and 0–5 proficiency. |
| `goal_competencies` | `(goal_id, competency_id)` | Goals associated with competencies. |
| `checkin_key_results` | `(checkin_id, key_result_id)` | Key results discussed in a check-in. |
| `feedback_competencies` | `(feedback_id, competency_id)` | Competencies associated with feedback. |
| `review_competencies` | `(review_id, competency_id)` | Competencies assessed by a review. |
| `development_plan_goals` | `(development_plan_id, goal_id)` | Goals addressed by a development plan. |
| `development_plan_competencies` | `(development_plan_id, competency_id)` | Competencies addressed by a development plan. |
| `evidence` | `id`: `EVD-000001` | Uploader employee, URI, media type, optional SHA-256, description, and exactly one FK target among key result, check-in, feedback, or review. |
| `review_approvals` | `(review_id, approver_manager_id)` | Review approval status, decision timestamp, and comments. Pending status has no decision time; final status requires one. |
| `development_plan_approvals` | `(development_plan_id, approver_manager_id)` | Development-plan approval status, decision timestamp, and comments with the same decision rule. |
| `entity_history` | `event_id`: generated UUID string | `entity_type`, `entity_id`, `actor_id`, optional `actor_employee_id`, action, JSONB before/after snapshots, recorded time. Triggers preserve core entity insert/update/delete (including Evidence) and bridge insert/update/delete events; history rows cannot be updated or deleted. Existing Evidence rows from before Evidence history was enabled are not backfilled. |

## ID generation

Counter-based primary keys are allocated in application code by `DeterministicIdAllocator` with dedicated counters and fixed seed `20261022`; no PostgreSQL sequences generate business IDs. Cycle, goal, key-result, and review IDs use the formatters in `backend/app/models/ids.py`. The database primary keys prevent duplicate IDs, while database checks enforce the required formats and embedded parent IDs. IDs are immutable after insertion. Goal progress is calculated by `backend/app/services/goal_progress.py` from key-result actuals, targets, and optional weights; incomplete results count as zero and progress is capped at 100%. No entity or synthetic rows are included in the initial migration.

Goal progress is a calculated percentage: each key result contributes `min(actual_value / target_value, 1)`. A missing actual counts as zero. If weights are supplied for all key results, they must be in the range 0–100 and sum to 100; otherwise key results are averaged equally. No independent goal-progress value is stored.

Call `set_audit_actor(session, employee_id)` before writes to associate them with an employee. The current transaction's audit actor is reset automatically when it ends; writes without an actor context are recorded as `SYSTEM`.

See [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) for relationship details, checks, indexes, and migration review instructions.
