# AI Order Intelligence

## Overview

This project solves the business problem of validating fuel order totals before processing, ensuring financial accuracy and reducing billing errors. Orders with mismatched totals are flagged for human review, creating an audit trail of validation decisions while maintaining correct order processing for valid submissions.

The system provides:
- Automated order validation through mathematical verification
- Human review workflow for questionable orders
- Complete audit trail with reviewer identity and timestamps
- Simple API for integration with order management systems

## Technologies

- **Python 3.13+**: Core application language
- **FastAPI**: REST API framework
- **SQLAlchemy 2.1.6**: ORM with async support
- **SQLite**: Local development database
- **aiosqlite 0.21.0**: Async SQLite driver
- **pytest 9.2.0**: Testing framework
- **anyio 4.15.1**: Async test support
- **Python-dotenv 1.2.4**: Environment configuration

## Implemented Features

- **Order Validation**:
  - Validates that `quantity × unit_price = stated_total` within tolerance
  - Automatically approves valid orders
  - Flags invalid orders for human review

- **Persistence Layer**:
  - Stores all orders with complete validation metadata
  - Tracks review status, reviewer identity, and timestamps
  - Uses safe migration strategy for schema changes

- **Human Review Workflow**:
  - Three review states: `APPROVED`, `PENDING_REVIEW`, `REJECTED`
  - Protected by reviewer API key authentication
  - Records reviewer identity from server configuration
  - Maintains complete audit trail with notes and timestamps

- **API Endpoints**:
  - `POST /validate-order`: Validates and persists orders
  - `GET /orders`: Retrieves all orders
  - `GET /orders/pending-review`: Retrieves orders needing review
  - `PATCH /orders/{order_id}/review`: Updates review status

## Architecture & Validation Flow

1. Client submits order with quantity, unit price, and stated total
2. API calculates expected total (quantity × unit price)
3. Compares expected vs. stated total with 0.01 tolerance
4. **Valid**: Auto-approved as `APPROVED`
5. **Invalid**: Flagged as `PENDING_REVIEW`
6. Reviewers can:
   - Approve → `APPROVED`
   - Reject → `REJECTED`
7. All state changes recorded with reviewer identity and timestamp

## API Documentation

### Validate Order (POST /validate-order)

**Request**:
```json
{
  "quantity": 100.0,
  "unit_price": 2.5,
  "stated_total": 250.0
}
```

**Successful Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "valid": true,
  "calculated_total": 250.0,
  "error": null
}
```

### Get All Orders (GET /orders)

**Response**:
```json
[{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "quantity": 100.0,
  "unit_price": 2.5,
  "stated_total": 250.0,
  "calculated_total": 250.0,
  "valid": true,
  "error": null,
  "review_status": "APPROVED",
  "reviewer": "Reviewer",
  "reviewed_at": "2026-10-30T16:28:02Z",
  "review_notes": null
}]
```

### Get Pending Review Orders (GET /orders/pending-review)

Returns only orders with `PENDING_REVIEW` status

### Review Order (PATCH /orders/{id}/review)

**Request**:
```json
{
  "decision": "APPROVE",
  "notes": "Valid after manual check"
}
```

**Headers**:
```
x-reviewer-key: reviewer_secret_key
```

**Validation Rules**:
- Only `APPROVE` or `REJECT` decisions allowed
- Only `PENDING_REVIEW` orders can be reviewed
- Requires valid reviewer API key

## Local Setup Instructions

### Windows (PowerShell)

```powershell
# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
Copy .env.example .env
# Edit .env with your values

# Run application
uvicorn main:app --reload --port 8000
```

### Mac/Linux (Bash)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Run application
uvicorn main:app --reload --port 8000
```

## Environment Configuration

**.env.example**:
```ini
# Reviewer API key for local development
REVIEWER_API_KEY=your_reviewer_key_here

# Reviewer name (must match your identity)
REVIEWER_NAME=your_name_here
```

> **Note**: Never commit actual credentials. Add `.env` to your `.gitignore`.

## Running Tests

```bash
pytest -v
```

**Test Results**:
```
13 passed, 0 failed, 0 skipped, 0 warnings in 4.57s
```

## Current Limitations

- **SQLite Database**: Suitable only for development (not production-scale)
- **No Production Authentication**: API key protection is basic (should integrate with proper auth system)
- **Local Development Focus**: No deployment configuration
- **No SSL/TLS**: HTTP only for local use
- **No Pagination**: `/orders` endpoint returns all records

## Future Improvements

- **AI-Powered PDF Order Extraction**: (Not implemented) Automatically extract order data from PDF invoices
- **Production Authentication**: Integrate with OAuth2 or corporate identity provider
- **Database Scaling**: Migrate to PostgreSQL for production
- **Review Dashboard**: Web interface for review workflow
- **Pagination & Filtering**: For large order volumes
- **Webhook Notifications**: Alert systems when orders require review