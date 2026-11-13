#!/bin/sh
set -eu

if [ -s /run/spoonfuls/postgres-password ] && [ -s /run/spoonfuls/app-password ]; then
  owner_password=$(cat /run/spoonfuls/postgres-password)
  app_password=$(cat /run/spoonfuls/app-password)
  export SPOONFULS_APP_PASSWORD="${SPOONFULS_APP_PASSWORD:-$app_password}"
  export MIGRATION_DATABASE_URL="${MIGRATION_DATABASE_URL:-postgresql://spoonfuls:${owner_password}@db:5432/spoonfuls}"
  export DATABASE_URL="${DATABASE_URL:-postgresql://spoonfuls_app:${app_password}@db:5432/spoonfuls}"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
