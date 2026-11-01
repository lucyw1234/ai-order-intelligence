# AI Order Intelligence

AI Order Intelligence is a FastAPI order-validation and human-review backend. It
checks whether a submitted order's stated total matches `quantity × unit_price`,
stores the order, and sends finite but mismatched totals to a reviewer. It does
not extract order data from documents and does not use an AI/ML model.

## Features

- Validates that quantity, unit price, and stated total are finite and positive.
- Automatically approves matching totals and flags mismatches as
  `PENDING_REVIEW`.
- Provides API-key-protected order listing and a reviewer-key-protected decision
  endpoint.
- Records reviewer, UTC review timestamp, and optional review notes.
- Uses SQLAlchemy async sessions, SQLite for local use, and Alembic migrations.

## Requirements

- Python 3.11 or newer
- Git

Install the project's runtime and migration dependencies from `requirements.txt`.
The PostgreSQL drivers support the existing async application URL and synchronous
Alembic runner.

## Local setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace the example values with unique local API keys and a
reviewer name. Never commit `.env` or use example keys outside local development.
The default database is the local `orders.db` SQLite file.

For a **new, empty local database**, create its schema with the checked-in
migrations:

```powershell
alembic upgrade head
```

Do not run this against a database containing records or a shared/production
database without first reviewing the target and obtaining approval. Application
startup initializes the engine and sessions only; it does not create, alter, or
migrate tables.

Start the API:

```powershell
uvicorn main:app --env-file .env --reload --port 8000
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## API demonstration

All order endpoints require `x-api-key`. A valid request is automatically
approved:

```powershell
curl.exe -X POST http://127.0.0.1:8000/validate-order `
  -H "x-api-key: <APP_API_KEY>" `
  -H "Content-Type: application/json" `
  -d "{\"quantity\": 2, \"unit_price\": 10, \"stated_total\": 20}"
```

A positive, finite but mismatched total is saved for review rather than rejected:

```powershell
curl.exe -X POST http://127.0.0.1:8000/validate-order `
  -H "x-api-key: <APP_API_KEY>" `
  -H "Content-Type: application/json" `
  -d "{\"quantity\": 2, \"unit_price\": 10, \"stated_total\": 19}"
```

List orders awaiting review with `GET /orders/pending-review`. To review an order,
use its returned ID:

```powershell
curl.exe -X PATCH http://127.0.0.1:8000/orders/<ORDER_ID>/review `
  -H "x-api-key: <APP_API_KEY>" `
  -H "x-reviewer-key: <REVIEWER_API_KEY>" `
  -H "Content-Type: application/json" `
  -d "{\"decision\": \"APPROVE\", \"notes\": \"Verified manually\"}"
```

The server requires `APP_API_KEY`, `REVIEWER_API_KEY`, and `REVIEWER_NAME`.
Missing key configuration fails closed. For local troubleshooting only, SQL
statement logging can be enabled by setting both `APP_ENV=development` and
`SQL_ECHO=true`; SQL logs may include submitted order values, so leave it off by
default.

## Tests

Activate the virtual environment and run:

```powershell
python -m pytest -v
```

The test configuration forces `TESTING=true` and an in-memory SQLite URL. A
database guard rejects file-backed SQLite and PostgreSQL URLs during tests.
Tables are created and dropped only in that disposable test database; tests do
not use the local application database.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/validate-order` | Validate and persist an order |
| `GET` | `/orders` | List orders |
| `GET` | `/orders/pending-review` | List orders requiring human review |
| `PATCH` | `/orders/{order_id}/review` | Approve or reject a pending order |

`POST /validate-order` returns HTTP 422 for zero, negative, or non-finite numeric
inputs. A finite, positive but incorrect stated total is persisted with
`PENDING_REVIEW`. Matching totals are automatically marked `APPROVED`.

## Current scope and limitations

This project demonstrates deterministic order-total validation and an
authenticated human-review workflow. PDF/image extraction, AI document
understanding, a web review dashboard, pagination, and production-grade
user/role authentication are not implemented. The API keys are a simple
portfolio/demo authentication mechanism, not a substitute for an identity
provider in production.
