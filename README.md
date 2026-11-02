# Notifications Challenge

[![Backend CI](https://github.com/GuillermoArielSequeira/notifications-challenge/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/GuillermoArielSequeira/notifications-challenge/actions/workflows/backend-ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/GuillermoArielSequeira/notifications-challenge/badge.svg?branch=master)](https://coveralls.io/github/GuillermoArielSequeira/notifications-challenge?branch=master)

## Overview

A full-stack take-home challenge to build a notification management system for authenticated users.

The application will support user authentication, notification management, and simulated delivery through multiple channels: Email, SMS, and Push Notifications.

**Current status:** Backend infrastructure, user registration, JWT login, and authenticated API access are implemented. Notification features and frontend implementation are pending.

## Live Deployment

The backend API is deployed on Render, using a managed PostgreSQL database hosted on Neon.

**Live URLs:**

- [Backend API](https://notifications-challenge.onrender.com)
- [Swagger Documentation](https://notifications-challenge.onrender.com/docs)
- [Health Check](https://notifications-challenge.onrender.com/health)

### Infrastructure

| Component | Provider |
|---|---|
| Backend | Render (Docker) |
| Database | Neon (PostgreSQL) |
| CI | GitHub Actions |
| Test Coverage | Coveralls |

### Deployment Configuration

The backend is deployed from the `master` branch using `backend/Dockerfile`.

Database credentials and connection settings are configured through Render environment variables and are not committed to the repository.

The deployment environment uses a separate PostgreSQL database from local development and testing.

### Environment Variables

The following environment variables are required:

```dotenv
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
POSTGRES_HOST=
POSTGRES_PORT=5432
POSTGRES_SSLMODE=require
POSTGRES_CHANNEL_BINDING=require
JWT_SECRET_KEY=<unique-random-secret-at-least-32-characters>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Database Migrations

Database schema changes are managed with Alembic.

`backend/start.sh` automatically runs `alembic upgrade head` before starting the API. Startup fails if migrations fail. Configure `JWT_SECRET_KEY` in Render before deploying authentication; no default signing key is provided.

### Free Tier Limitations

The Render free instance may become inactive after periods without traffic. The first request after inactivity may take longer to respond.

This deployment is intended for demonstration and technical evaluation rather than production workloads.

## Tech Stack

**Backend**
- Python 3.13
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL 17

**Frontend (planned)**
- React
- TypeScript
- Vite

**Infrastructure & Testing**
- Docker and Docker Compose
- pytest, HTTPX and pytest-cov
- GitHub Actions
- Coveralls

## Project Structure

```text
notifications-challenge/
├── .github/workflows/      # CI workflows
├── backend/
│   ├── app/
│   │   ├── core/           # Configuration and database
│   │   ├── routers/        # API endpoints
│   │   ├── schemas/        # Pydantic schemas
│   │   └── main.py         # FastAPI application
│   ├── migrations/         # Alembic migrations
│   ├── tests/              # Automated tests
│   ├── Dockerfile
│   ├── Dockerfile.test
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/               # React application (planned)
├── docker-compose.yml
├── docker-compose.test.yml
├── up_dev.sh
├── up_test.sh
└── README.md
```

## Getting Started

### Prerequisites

- Git
- Docker Desktop with Docker Compose
- Available local ports: 8000, 5433 and 5434

Python does not need to be installed locally when running the application through Docker.

### 1. Clone the repository

```bash
git clone https://github.com/GuillermoArielSequeira/notifications-challenge.git

cd notifications-challenge
```

### 2. Configure environment variables

For a fresh installation, create an `.env` file from the provided example:

```bash
cp .env.example .env
```

Configure the following variables:

```dotenv
POSTGRES_USER=notifications
POSTGRES_PASSWORD=your_local_password
POSTGRES_DB=notifications_db
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
```

Replace `your_local_password` with your own development password.

Generate a signing secret with `openssl rand -hex 32` and set `JWT_SECRET_KEY` in the root `.env`. The key must contain at least 32 characters; use a different random key in each environment. `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` defaults to `30` (allowed range: 1–1440).

The `.env` file is excluded from Git. Never commit real credentials.

### 3. Start the application

```bash
./up_dev.sh
```

This command builds and starts:

- FastAPI on `localhost:8000`.
- PostgreSQL on `localhost:5433`.

Docker Compose also waits for the database health check before starting the API.

### 4. Database migrations

API startup applies migrations automatically. To apply them manually to the running development environment:

```bash
docker compose exec api python -m alembic upgrade head
```

This applies the available Alembic migrations to the development database.

### 5. Access the API

| Resource | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| OpenAPI schema | http://localhost:8000/openapi.json |
| Health check | http://localhost:8000/health |
| Ping | http://localhost:8000/api/v1/ping |
| Database check | http://localhost:8000/api/v1/db-check |

`/health`, `/docs`, and `/openapi.json` are public. `/`, `/api/v1/ping`, and `/api/v1/db-check` require a bearer token, as do the protected application routes.

## Authentication

Both authentication endpoints accept JSON. Email addresses are validated, trimmed, and stored lowercase; accounts treat email addresses as case-insensitive. Registration passwords must contain 8–128 characters and are stored as salted Argon2id hashes, never plaintext. Passwords are not trimmed or normalized.

```bash
# Register: 201 with id, email, created_at; 409 if email is already registered.
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"a-long-example-password"}'

# Login: 200 with access_token, token_type (bearer), expires_in (seconds).
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"a-long-example-password"}'

# Supply the returned access_token to protected endpoints.
curl http://localhost:8000/api/v1/users/me \
  -H 'Authorization: Bearer <access_token>'
```

In Swagger UI, paste the token into **Authorize**. Missing, invalid, expired tokens and tokens for deleted/nonexistent users receive `401` with `WWW-Authenticate: Bearer`. Incorrect login credentials return the same generic error whether or not the email exists. Invalid request bodies return `422` without echoing input values.

Access tokens are HS256-signed JWTs with required `sub`, `iat`, and `exp` claims. Use HTTPS outside local development. This initial scope does not include refresh tokens, logout/revocation, password recovery, email verification, roles, or rate limiting. Tokens remain valid until expiration unless the user is deleted or the signing key changes.

### Validation errors

Every `422` validation response uses a `detail` list with exactly three properties per error: a machine-readable `type`, the affected `field`, and a user-facing Spanish `message`. For example:

```json
{
  "detail": [
    {
      "type": "invalid_email",
      "field": "email",
      "message": "Ingresá un email válido."
    },
    {
      "type": "password_too_short",
      "field": "password",
      "message": "La contraseña debe tener al menos 8 caracteres."
    }
  ]
}
```

Other codes include `password_too_long`, `required_field`, `invalid_type`, `invalid_json`, and `invalid_body`. Fields omit request-source prefixes such as `body`; nested fields retain their full path (for example, `users.0.email`). Errors affecting the whole request body use `"field": null`. Responses never include submitted values, internal validation context, or raw validator messages. Swagger documents this same response schema. Authentication errors (`401`) and duplicate-email errors (`409`) keep their existing format.

## Database

PostgreSQL runs inside Docker, with isolated development and testing environments.

| Environment | Host | Port | Database |
|---|---|---|---|
| Development | localhost | 5433 | Configured in `.env` |
| Testing | localhost | 5434 | notifications_test |

Within Docker Compose, services use Docker service names and internal port `5432` to communicate.

### Database Migrations

Alembic manages database schema changes.

From the `backend` directory, with the Python virtual environment activated and PostgreSQL running:

```bash
# Check current revision
alembic current

# Generate a migration from model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Revert one migration
alembic downgrade -1
```

Migration generation requires the SQLAlchemy models to be imported into Alembic's metadata configuration. Generated migrations should be reviewed before applying them.

## Testing

Tests are implemented with pytest and FastAPI's TestClient. The suite covers registration, password hashing, login, JWT validation, route protection, database connectivity, and migration/model consistency.

The test environment uses a separate PostgreSQL container to avoid modifying development data.

### Run tests using Docker

```bash
./up_test.sh
```

This command builds the testing image, starts the testing database when required, executes pytest, and generates a coverage report.

To run one test, rebuilding the image to include source changes:

```bash
docker compose -f docker-compose.test.yml run --rm --build tests \
  python -m pytest -v tests/test_auth.py::test_login_and_me
```

The test fixture applies Alembic migrations to `notifications_test`, then uses an outer transaction and savepoints to roll back each database-backed test even when application code commits. It accepts only the local test database (hosts `localhost`, `127.0.0.1`, `::1`, or Docker's `db_test`); it never migrates the development database. Docker tests use a test-only signing key and do not require the root `.env`.

### Run tests locally

Python 3.13 and the development dependencies must be installed.

```bash
# From the repository root:
docker compose -f docker-compose.test.yml up -d --wait db_test

cd backend

python3.13 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements-dev.txt
python -m pytest -v
```

When tests are executed locally, the PostgreSQL testing container must be available on `localhost:5434`.

The fixtures supply test-only configuration before importing the application, so local tests also do not require a development `.env`. `TEST_DATABASE_URL` can override the test connection but must still target the isolated local `notifications_test` database. Security-only tests can run without PostgreSQL: `python -m pytest -v tests/test_security.py` from `backend/`.

### Test Coverage

Coverage is generated automatically when running tests through Docker.

The report is saved to:

```text
coverage/coverage.xml
```

Database data is rolled back between tests; migrations remain applied in the test database.

## Continuous Integration

GitHub Actions automatically runs the backend tests on pushes and pull requests.

The workflow:

1. Checks out the repository.
2. Configures Docker Compose.
3. Executes the Docker-based test suite.
4. Verifies the generated coverage report.
5. Uploads coverage results to Coveralls.

Workflow configuration: `.github/workflows/backend-ci.yml`.

## Architecture

Authentication follows a layered architecture: `app/routers/auth.py` handles HTTP, `app/services/auth.py` orchestrates registration/login, `app/repositories/users.py` handles persistence, and `app/models/user.py` defines the user table. Security helpers and the `get_current_user` dependency live in `app/core/`. Future features should follow the same separation.

```text
Controller
    ↓
Service
    ↓
Repository
    ↓
SQLAlchemy Models
    ↓
PostgreSQL
```

**Layer responsibilities:**

- **Controller:** Handle HTTP requests, authentication dependencies, input validation, and responses.
- **Service:** Implement application use cases and business rules.
- **Repository:** Encapsulate persistence operations and database access.
- **Models:** Define database entities and relationships using SQLAlchemy.
- **Schemas:** Define request and response contracts using Pydantic.

Database sessions, the authentication service, and authenticated users are provided via FastAPI dependency injection. `app/core/dependencies.py` assembles `AuthService` through `get_auth_service`; auth endpoints receive `AuthServiceDependency` instead of constructing services or repositories. Tests can override `get_auth_service` through `app.dependency_overrides` to exercise HTTP behavior without a database. In `app/main.py`, public auth routes are mounted separately from `protected_api`; attach future protected routers to `protected_api` so they inherit authentication.

### Notification Delivery Strategy (Planned)

The notification system will use the Strategy Pattern to support multiple delivery channels.

Each channel will have its own implementation for validation, formatting, and simulated delivery.

The goal is to make new channels extensible without changing the notification orchestration logic.

## Technical Decisions

**FastAPI:** Provides a lightweight REST API framework with automatic OpenAPI documentation and dependency injection.

**SQLAlchemy:** Separates database operations from HTTP handling and provides ORM support.

**Alembic:** Versions database schema changes, allowing consistent setup across environments.

**PostgreSQL:** Provides relational persistence for users and notifications.

**Docker:** Ensures reproducible development and testing environments without requiring local PostgreSQL installation.

**Separate testing database:** Prevents tests from interfering with development data.

**GitHub Actions and Coveralls:** Automate test execution and coverage reporting.

## Roadmap

- [x] Project bootstrap and FastAPI setup
- [x] Swagger documentation
- [x] PostgreSQL integration
- [x] SQLAlchemy and Alembic configuration
- [x] Initial automated tests
- [x] Docker development and testing environments
- [x] GitHub Actions and Coveralls
- [x] Deployment
- [x] User registration and authentication
- [ ] Notification CRUD
- [ ] Email, SMS, and Push delivery strategies
- [ ] React frontend

## Development Commands

```bash
# Start development services
./up_dev.sh

# Run tests
./up_test.sh

# Display running containers
docker compose ps

# View backend logs
docker compose logs -f api

# Stop development services
docker compose stop api db
```

## License

This project was created for educational purposes as part of a technical take-home challenge.
