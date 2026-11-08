# AGENTS.md — Notifications Challenge

A full-stack take-home challenge for an authenticated notification management system. Prioritize maintainable code, clear responsibilities, and automated verification.

## Current scope
- Están implementados la infraestructura backend, los endpoints de diagnóstico, el registro, el login JWT, el acceso autenticado y el CRUD de notificaciones propias.
- Notificaciones expone POST/GET `/api/v1/notifications` y PATCH/DELETE `/api/v1/notifications/{notification_id}`, protegidos por JWT y filtrados por propietario. El borrado es definitivo; los recursos ajenos e inexistentes comparten el mismo 404.
- Las estrategias de envío y el frontend React siguen pendientes. El CRUD almacena notificaciones, no las envía.
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
- Las fixtures aplican migraciones a `notifications_test` y aíslan cada test con una transacción externa y savepoints, incluso cuando la aplicación hace commit.

## Working agreement
- Inspect existing code and conventions before making changes.
- Antes de implementar cambios funcionales, obtener aprobación de la spec, el plan y las tareas según la skill `sdd`.
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

## Spec-Driven Development
- Cargar la skill `sdd` para trabajar con specs, planes, tareas o su implementación. Cada funcionalidad vive en `specs/NNN-nombre/`, con `spec.md`, `plan.md` y `tasks.md`.
- `docs/constitution.md` fija los principios; la spec aprobada define el comportamiento y el alcance; `AGENTS.md` contiene instrucciones operativas.
- `MEMORY.md` indica la spec activa, la fase, las aprobaciones, el próximo paso y los bloqueos; no duplica requisitos ni listas de tareas.
- Las skills aportan guías técnicas, pero no autorizan cambios de alcance ni sustituyen las decisiones aprobadas. Ante contradicciones entre documentos o con el código, señalarlas y pedir una decisión antes de continuar con el trabajo afectado.
- Aplicar SDD a cambios nuevos; no crear specs retrospectivas ni refactorizar lo existente solo para adoptar el proceso.

## Boundaries
- Ask before adding major dependencies, changing architecture, or modifying deployment configuration.
- Never expose secrets, run destructive database operations, or modify production data without explicit approval.
- Do not commit or push changes unless requested.

## Project context
- Consultar `docs/constitution.md`, `MEMORY.md` y los documentos de la spec activa en `specs/NNN-nombre/` antes de proponer o implementar cambios. Si no hay spec activa, no asumir una: proponerla y esperar aprobación.
- Refer to `README.md` for setup, infrastructure, and architectural overview.
- If `MEMORY.md` exists, read it at the start of significant work and update only meaningful decisions, pitfalls, and pending tasks.
