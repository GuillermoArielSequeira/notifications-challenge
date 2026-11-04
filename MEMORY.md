# MEMORY.md — Notifications Challenge

Shared project memory for AI development sessions. Keep it concise and focused on current progress, relevant decisions, known issues, and next steps.

## Current Status

- Backend infrastructure is complete: FastAPI, SQLAlchemy, PostgreSQL, Alembic, Docker, and pytest.
- GitHub Actions runs automated tests and uploads coverage to Coveralls.
- The backend is deployed on Render and uses PostgreSQL hosted on Neon.
- Database migrations run automatically before FastAPI starts.
- User registration, JSON login with JWT access tokens, and `/api/v1/users/me` are implemented alongside diagnostic endpoints.
- API routes require a bearer token except registration, login, `/health`, and documentation. Future protected routers belong under `protected_api` in `app/main.py`.
- Notification management, delivery strategies, and the frontend are pending.
- Última verificación backend registrada antes de esta adaptación SDD: `./up_test.sh` pasó 74 tests con PostgreSQL 17 y 99% de cobertura. Es un resultado histórico, no una nueva ejecución ni garantía del estado actual.

## Trabajo activo
- Spec: ninguna activa; `specs/001/` existe vacía y se conserva sin renombrar.
- Fase: adaptación del flujo SDD aplicada y comprobada documentalmente; sin implementación de una funcionalidad ni validación nueva del backend.
- Aprobaciones: adaptación del flujo aprobada; spec, plan y tareas de la próxima funcionalidad todavía no definidos ni aprobados.
- Próximo paso: activar Docker y repetir `./up_test.sh`; después acordar la siguiente funcionalidad y redactar su spec antes de proponer el plan técnico.
- Verificación de la adaptación: metadatos YAML, referencias, límites de la constitución y `git diff --check` comprobados correctamente, sin instalar dependencias.
- Bloqueos: `./up_test.sh` no pudo iniciar la suite porque Docker no está activo; no hay bloqueos de requisitos identificados.

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

## Next Steps
- Add notification CRUD and ownership checks using the authenticated user dependency.
- Before production use, address rate limiting, email verification, password recovery, and token lifecycle requirements.
