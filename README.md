# Búvoli Appka — Livestock Management Platform

Regional livestock management web application for Czech agricultural cooperatives (JZDs).

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Alembic
- **Database:** PostgreSQL 15+ with JSONB and PostGIS
- **Frontend:** Jinja2 templates, Bootstrap 5, Alpine.js, Leaflet.js
- **Auth:** JWT in HttpOnly cookies
- **Cache / task queue:** Redis + Celery
- **Email:** aiosmtplib

## Quick start

```bash
# 1. Install dependencies
poetry install

# 2. Copy and fill env file
cp .env.example .env

# 3. Start PostgreSQL and Redis (Docker example)
docker run -d --name pg -e POSTGRES_DB=buvoli -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15
docker run -d --name redis -p 6379:6379 redis:7

# 4. Run migrations
poetry run alembic upgrade head

# 5. Create initial SUPER_ADMIN
poetry run python -m app.cli create-superadmin

# 6. Start the app
poetry run uvicorn app.main:app --reload
```

## Project structure

```
app/
  config.py          — pydantic-settings config
  database.py        — SQLAlchemy engine + session
  main.py            — FastAPI app + router registration
  dependencies.py    — shared FastAPI dependencies (auth, pagination)
  middleware/
    jzd_context.py   — sets request.state.jzd_id from JWT
  models/            — SQLAlchemy ORM models
  schemas/           — Pydantic request/response schemas
  routers/           — FastAPI route handlers
  services/          — business logic
  templates/         — Jinja2 HTML templates
  static/            — CSS, JS, images
alembic/             — database migrations
```

## Roles

| Role | Scope |
|---|---|
| `SUPER_ADMIN` | Full system access, provisions JZDs and users |
| `JZD_ADMIN` | Full access within own JZD |
| `FARM_OWNER` | Manage own farms and livestock |
| `INSEMINATOR` | Read all JZDs, schedule inseminations, record procedures |
| `SPERM_COLLECTOR` | Read all JZDs, schedule viewings |
| `VETERINARIAN` | Read all JZDs, manage health records, confirm pregnancies |

## Czech cattle registration number

Registration numbers follow EU Regulation 1760/2000:
- Format: `CZ` + 12-digit national number
- Example: `CZ000123456789`
- Auto-generate uses a zero-padded sequential counter scoped to the JZD

## ⚠️ POC performance note — Breeding Match algorithm

The outcome-based breeding match (`POST /api/v1/search/breeding-match`) uses a brute-force
O(cows × bulls) scoring loop. This is intentional for the POC — correctness over performance.

**Production path:**
1. Pre-filter candidates by location (PostGIS `ST_DWithin`) before scoring to shrink the pool
2. Vectorise scoring with NumPy (replace Python loops with array operations)
3. Move computation to a Celery task; return a `task_id` immediately, poll for results
4. Cache results in Redis keyed on a hash of the search criteria (TTL 10 min)
5. Long-term: pre-compute pairwise scores nightly and store in `breeding_match_score` table;
   serve from table at query time, refresh incrementally on livestock updates

At 1 000 cows × 500 bulls the current loop runs in ~50 ms locally; at 10 000 × 5 000 it will
be too slow for a synchronous response — apply step 3 before that scale.
