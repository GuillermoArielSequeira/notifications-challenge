# Notifications Challenge

[![Backend CI](https://github.com/GuillermoArielSequeira/notifications-challenge/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/GuillermoArielSequeira/notifications-challenge/actions/workflows/backend-ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/GuillermoArielSequeira/notifications-challenge/badge.svg?branch=master)](https://coveralls.io/github/GuillermoArielSequeira/notifications-challenge?branch=master)

## Overview

A full-stack take-home challenge to build a notification management system for authenticated users.

The application will support user authentication, notification management, and simulated delivery through multiple channels: Email, SMS, and Push Notifications.

**Current status:** Infrastructure and testing setup completed. Business features and frontend implementation are pending.

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

The `.env` file is excluded from Git. Never commit real credentials.

### 3. Start the application

```bash
./up_dev.sh
```

This command builds and starts:

- FastAPI on `localhost:8000`.
- PostgreSQL on `localhost:5433`.

Docker Compose also waits for the database health check before starting the API.

### 4. Apply database migrations

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

These are currently infrastructure and diagnostic endpoints, not the final business API.

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

Tests are implemented with pytest and FastAPI's TestClient.

The test environment uses a separate PostgreSQL container to avoid modifying development data.

### Run tests using Docker

```bash
./up_test.sh
```

This command builds the testing image, starts the testing database when required, executes pytest, and generates a coverage report.

### Run tests locally

Python 3.13 and the development dependencies must be installed.

```bash
cd backend

python3.13 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements-dev.txt
python -m pytest -v
```

When tests are executed locally, the PostgreSQL testing container must be available on `localhost:5434`.

### Test Coverage

Coverage is generated automatically when running tests through Docker.

The report is saved to:

```text
coverage/coverage.xml
```

The initial test suite covers basic API health checks and database connectivity. Business logic tests will be added as features are implemented.

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

The backend will follow a modular, layered architecture inspired by Clean Architecture.

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

**Planned responsibilities:**

- **Controller:** Handle HTTP requests, authentication dependencies, input validation, and responses.
- **Service:** Implement application use cases and business rules.
- **Repository:** Encapsulate persistence operations and database access.
- **Models:** Define database entities and relationships using SQLAlchemy.
- **Schemas:** Define request and response contracts using Pydantic.

The implementation will use dependency injection to reduce coupling and improve testability.

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
- [ ] Deployment
- [ ] User registration and authentication
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
