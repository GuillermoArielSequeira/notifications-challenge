# MEMORY.md — Notifications Challenge

Shared project memory for AI development sessions. Keep it concise and focused on current progress, relevant decisions, known issues, and next steps.

## Current Status

- Backend infrastructure is complete: FastAPI, SQLAlchemy, PostgreSQL, Alembic, Docker, and pytest.
- GitHub Actions runs automated tests and uploads coverage to Coveralls.
- The backend is deployed on Render and uses PostgreSQL hosted on Neon.
- Database migrations run automatically before FastAPI starts.
- User registration, JSON login with JWT access tokens, and `/api/v1/users/me` are implemented alongside diagnostic endpoints.
- API routes require a bearer token except registration, login, `/health`, and documentation. Future protected routers belong under `protected_api` in `app/main.py`.
- El CRUD HTTP de notificaciones propias está implementado con autenticación JWT, edición parcial, borrado definitivo y aislamiento entre propietarios. Estrategias de envío y frontend siguen pendientes. Estos cambios no fueron desplegados.
- Última verificación backend: el 2026-11-08, `./up_test.sh` pasó 426 tests con Python 3.13.18 y PostgreSQL 17, 99% de cobertura global y 100% en los módulos de notificaciones. Se comprobaron servicio, repositorio, CRUD HTTP, validaciones, autenticación, aislamiento, OpenAPI y regresiones de migraciones; reporte XML generado.

## Trabajo activo
- Spec: [001 — Gestión de notificaciones propias](specs/001-notifications/spec.md), aprobada explícitamente por el usuario; la carpeta vacía `specs/001/` se renombró según la propuesta aprobada.
- Fase: T1–T7 completadas y verificadas técnicamente; pendiente conformidad del usuario para cerrar la spec.
- Aprobaciones: spec, [plan técnico](specs/001-notifications/plan.md) y [tareas](specs/001-notifications/tasks.md) aprobados; el 2026-11-08 el usuario autorizó terminar T4–T7 sin pausas y recibir solo el resultado final. No supone conformidad anticipada para cerrar la spec.
- Próximo paso: recibir conformidad con el resultado final antes de cambiar `spec.md` a implementada; no asumir otra spec ni iniciar envíos o frontend.
- Verificación actual: tests primero con rojo/verde por tarea; suite completa de 426 tests y comprobaciones de OpenAPI, XML, formato y enlaces correctas. Evidencias en `tasks.md`. Solo se usó `notifications_test`; desarrollo y producción intactos.
- Bloqueos técnicos: ninguno. Docker Desktop se inició porque estaba detenido; las verificaciones posteriores pasaron.

## Decisions and Rationale

### Adopción de SDD
- **Decisión:** Usar la skill local `sdd` y una sola carpeta por funcionalidad con spec, plan y tareas; conservar la constitución y las skills de Python, sin incorporar Superpowers ni dependencias nuevas.
- **Motivo:** Mantener aprobaciones explícitas, trazabilidad entre requisitos y tests y ejecución de una tarea por vez, con un proceso entendible para quien empieza a programar. La adopción no crea specs retrospectivas ni modifica la aplicación.

### Constitución del proyecto
- **Decisión:** Se aprobó `docs/constitution.md` y se enlazó desde `AGENTS.md`.
- **Motivo:** Mantener criterios verificables de alcance, sencillez y seguridad para que alguien que empieza a programar pueda mantener el challenge, sin refactorizar lo existente como parte de esta adopción.

### Deployment migrations
- **Decision:** Execute Alembic migrations during application startup using `backend/start.sh`.
- **Reason:** The current deployment uses a single Render instance on the free plan. This provides a simple automated migration process without requiring a separate deployment job.
- **Revisit when:** Moving to multiple application instances or a production deployment requiring independent migration execution.

### Project-local agent skills
- **Decision:** Install `python-anti-patterns`, `python-error-handling`, and `python-testing-patterns` from `wshobson/agents` in `.agents/skills/`, with installation metadata in `skills-lock.json`. `python-project-structure` remains optional and is not installed.
- **Reason:** Add review, error-handling, and testing guidance for this repository without a global skill installation or application refactor.

## Known Issues and Learnings

- Docker development images do not use source bind mounts. Code changes require rebuilding the image.
- Database fixtures apply Alembic migrations through an explicit test connection, then isolate each test with an outer transaction and savepoints so application commits can be rolled back. Only the local `notifications_test` database is accepted.
- A random `JWT_SECRET_KEY` of at least 32 characters is now required before API startup, including Render deployment. `.env.example` deliberately leaves it empty; tests supply their own key. Token TTL defaults to 30 minutes.

### Authentication decisions
- **Decision:** Use Argon2id (`pwdlib`) for passwords and HS256 JWT access tokens (`PyJWT`) with mandatory subject, issue time, and expiration. No refresh/revocation flow in this scope.
- **Reason:** Keep the challenge implementation small while avoiding custom cryptography; checking that the subject user still exists also rejects deleted-user tokens.
- **Decision:** Normalize validated emails to lowercase and enforce uniqueness in PostgreSQL, handling constraint violations rather than relying on a pre-check.
- **Reason:** Case-insensitive account identity and safe duplicate handling even with concurrent registration requests.
- **Decision:** Use HTTP bearer authentication with JSON login rather than an OAuth2 password form.
- **Reason:** Match the requested email/password API without a form-parser dependency; Swagger still supports bearer authorization.
- **Decision:** Assemble `AuthService` in `get_auth_service` (`app/core/dependencies.py`) and inject it into auth endpoints using `AuthServiceDependency`.
- **Reason:** Keep service/repository construction out of HTTP handlers and allow service overrides for database-free router tests. This remains a pragmatic layered architecture; no repository interfaces or separate domain entities were introduced.

### Validation error responses
- **Decision:** Keep HTTP 422 and the `detail` list, but expose only `type`, `field`, and a Spanish `message` per validation error. Whole-body errors use a null field; nested paths retain their indices. HTTP 401 and 409 formats remain unchanged.
- **Reason:** Provide clear, machine-readable errors without leaking submitted values or internal validator messages. `app/core/exception_handlers.py` formats errors and `app/schemas/errors.py` defines the shared response/OpenAPI contract.

### Notificaciones propias
- **Decisión:** Buscar conjuntamente por UUID y propietario antes de editar/borrar y usar la misma excepción/404 para recursos ajenos e inexistentes, para no revelar su existencia. Los routers reciben el servicio inyectado y no construyen repositorios.
- **Decisión:** Extraer PATCH con `model_dump(exclude_unset=True)` tras validar con Pydantic; el servicio mantiene la lista de campos permitidos. Así se conservan omisiones sin aceptar null, cambios de identidad o asignación arbitraria de atributos desde HTTP.

## Next Steps
- Cerrar la spec 001 solo tras la conformidad del usuario; acordar una nueva spec antes de abordar envíos o frontend.
- Before production use, address rate limiting, email verification, password recovery, and token lifecycle requirements.
