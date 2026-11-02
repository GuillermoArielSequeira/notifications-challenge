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
- Backend verification: `./up_test.sh` passes all 74 tests on PostgreSQL 17 with 99% application coverage, including authentication, service injection, migration/model consistency, database isolation, and the custom validation error contract.

## Decisions and Rationale

### Deployment migrations
- **Decision:** Execute Alembic migrations during application startup using `backend/start.sh`.
- **Reason:** The current deployment uses a single Render instance on the free plan. This provides a simple automated migration process without requiring a separate deployment job.
- **Revisit when:** Moving to multiple application instances or a production deployment requiring independent migration execution.

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
