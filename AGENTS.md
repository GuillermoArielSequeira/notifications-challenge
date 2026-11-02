# AGENTS.md — Notifications Challenge

A full-stack take-home challenge for an authenticated notification management system. Prioritize maintainable code, clear responsibilities, and automated verification.

## Current scope
- Only backend infrastructure and diagnostic endpoints are implemented.
- Authentication, notification CRUD, delivery strategies, and the React frontend are planned, not implemented.
- Never assume a planned component or abstraction already exists.

## Stack and structure
- Backend: Python 3.13, FastAPI, Pydantic, SQLAlchemy 2 (synchronous), Alembic, PostgreSQL 17.
- Frontend (planned): React, TypeScript, Vite.
- Backend entrypoint: `backend/app/main.py`; API routers live under `backend/app/routers/`.
- Database sessions use FastAPI dependency injection via `app.core.database.get_db`.

## Development commands
- Run Docker Compose commands from the repository root.
- `./up_dev.sh`: build and start the API and development database.
- `./up_test.sh`: run the Docker-based test suite with coverage.
- `docker compose logs -f api`: inspect API logs.
- Docker images copy source files; rebuild after code changes.
- Root `.env` contains local configuration. Never commit credentials.

## Architecture and conventions
- Follow a feature-oriented, layered architecture: Controller → Service → Repository → Models.
- Controllers handle HTTP concerns; services own business logic; repositories handle database access.
- Use Pydantic for API contracts and SQLAlchemy for persistence models.
- Use design patterns when appropriate, selecting the most suitable pattern for each use case. Avoid forcing patterns or introducing unnecessary complexity.
- Keep implementations simple; avoid unnecessary abstractions and dependencies.
- Use descriptive English identifiers and follow existing code conventions.

## Database and testing
- Development and testing use separate PostgreSQL databases; never run tests against production.
- `backend/start.sh` runs `alembic upgrade head` before starting FastAPI.
- Import new SQLAlchemy models into Alembic metadata configuration before autogenerating migrations.
- Review generated migrations before applying them.
- Use the `db_test_client` fixture for database-backed API tests.
- Tests do not currently initialize schema or roll back changes automatically; add appropriate test isolation when needed.

## Working agreement
- Inspect existing code and conventions before making changes.
- For nontrivial features or architectural changes, propose a short plan before implementation.
- Prefer small, focused changes; avoid unrelated refactors and extra features.
- Add or update tests when implementing business logic.
- After changes, report modified files, verification results, and relevant decisions.
- Never claim tests or commands passed unless they actually ran.

## Project Memory
- Update MEMORY.md after meaningful milestones, important decisions, or discoveries.
- Record decisions together with their rationale, not just the chosen solution.
- Remove outdated information instead of accumulating a historical log.
- Keep permanent development rules in AGENTS.md, not MEMORY.md.
- Never store credentials, tokens, or sensitive information.

## Boundaries
- Ask before adding major dependencies, changing architecture, or modifying deployment configuration.
- Never expose secrets, run destructive database operations, or modify production data without explicit approval.
- Do not commit or push changes unless requested.

## Project context
- Refer to `README.md` for setup, infrastructure, and architectural overview.
- If `MEMORY.md` exists, read it at the start of significant work and update only meaningful decisions, pitfalls, and pending tasks.
