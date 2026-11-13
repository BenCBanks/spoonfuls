"""Database connection and append-only migrations for Spoonfuls."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg


# Add new migrations to the end of this list. Never edit a migration after it
# has shipped: deployed databases record each number in schema_migrations.
MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "users-and-sessions",
        """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;

        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
        ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

        CREATE POLICY users_own_rows ON users
            USING (id = NULLIF(current_setting('app.user_id', true), '')::uuid);
        CREATE POLICY sessions_own_rows ON sessions
            USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);
        """,
    ),
]


def database_url() -> str:
    """Return the configured PostgreSQL URL without embedding a secret in code."""

    return os.environ.get("DATABASE_URL", "postgresql://spoonfuls@localhost:5432/spoonfuls")


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """Yield a short-lived connection and close it on exit."""

    with psycopg.connect(database_url()) as conn:
        yield conn


def apply_migrations() -> None:
    """Apply each numbered migration once, in order."""

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            applied = {row[0] for row in cur.fetchall()}
            for version, name, sql in MIGRATIONS:
                if version in applied:
                    continue
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                    (version, name),
                )


def is_ready() -> bool:
    """Check that PostgreSQL accepts a connection."""

    try:
        with connection() as conn:
            conn.execute("SELECT 1")
        return True
    except (OSError, psycopg.Error):
        return False
