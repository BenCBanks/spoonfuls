#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ] && [ -s /run/spoonfuls/postgres-password ]; then
  password=$(cat /run/spoonfuls/postgres-password)
  export DATABASE_URL="postgresql://spoonfuls:${password}@db:5432/spoonfuls"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
