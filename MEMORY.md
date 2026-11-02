# MEMORY.md — Notifications Challenge

Shared project memory for AI development sessions. Keep it concise and focused on current progress, relevant decisions, known issues, and next steps.

## Current Status

- Backend infrastructure is complete: FastAPI, SQLAlchemy, PostgreSQL, Alembic, Docker, and pytest.
- GitHub Actions runs automated tests and uploads coverage to Coveralls.
- The backend is deployed on Render and uses PostgreSQL hosted on Neon.
- Database migrations run automatically before FastAPI starts.
- Only infrastructure and diagnostic endpoints are implemented.
- Authentication, notification management, delivery strategies, and the frontend are pending.

## Decisions and Rationale

### Deployment migrations
- **Decision:** Execute Alembic migrations during application startup using `backend/start.sh`.
- **Reason:** The current deployment uses a single Render instance on the free plan. This provides a simple automated migration process without requiring a separate deployment job.
- **Revisit when:** Moving to multiple application instances or a production deployment requiring independent migration execution.

## Known Issues and Learnings

- Docker development images do not use source bind mounts. Code changes require rebuilding the image.
- Database-backed tests use a separate PostgreSQL instance, but the current fixtures do not automatically create tables, apply migrations, or roll back database changes.
- Before implementing database-backed business tests, introduce proper test schema initialization and isolation.
- The README's production migration instructions should be updated to reflect automatic execution through `backend/start.sh`.

## Next Steps

