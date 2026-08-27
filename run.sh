#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── Services ────────────────────────────────────────────────────────────────
echo "Starting PostgreSQL and Redis..."
brew services start postgresql@16 2>/dev/null || true
brew services start redis 2>/dev/null || true

# ── Migrations ──────────────────────────────────────────────────────────────
echo "Running migrations..."
poetry run alembic upgrade head

# ── App ─────────────────────────────────────────────────────────────────────
echo "Starting Búvoli at http://localhost:8000"
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
