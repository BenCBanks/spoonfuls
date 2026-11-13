"""Database connection and append-only migrations for Spoonfuls."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import sql

APP_ROLE = "spoonfuls_app"


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
            email TEXT NOT NULL,
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
        ALTER TABLE users FORCE ROW LEVEL SECURITY;
        ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE sessions FORCE ROW LEVEL SECURITY;

        CREATE UNIQUE INDEX users_email_lower_idx ON users (lower(email));

        CREATE POLICY users_own_rows ON users
            USING (id = NULLIF(current_setting('app.user_id', true), '')::uuid);
        CREATE POLICY sessions_own_rows ON sessions
            USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);

        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO spoonfuls_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO spoonfuls_app;
        """,
    ),
    (
        2,
        "accounts-and-auth-functions",
        """
        ALTER TABLE users
            ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE sessions
            ADD COLUMN csrf_token_hash TEXT;

        CREATE TABLE invites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code_hash TEXT NOT NULL UNIQUE,
            created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        ALTER TABLE invites ENABLE ROW LEVEL SECURITY;
        ALTER TABLE invites FORCE ROW LEVEL SECURITY;

        CREATE POLICY invites_admin_rows ON invites
            USING (
                created_by = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = invites.created_by AND users.is_admin
                )
            )
            WITH CHECK (
                created_by = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = invites.created_by AND users.is_admin
                )
            );

        CREATE POLICY sessions_by_token ON sessions
            FOR SELECT
            USING (token_hash = current_setting('app.session_hash', true));

        CREATE OR REPLACE FUNCTION lookup_user_for_login(lookup_email TEXT)
        RETURNS TABLE(user_id UUID, password_hash TEXT)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
        AS $$
            SELECT id, password_hash
            FROM users
            WHERE lower(email) = lower(trim(lookup_email))
            LIMIT 1
        $$;

        CREATE OR REPLACE FUNCTION spoonfuls_has_users()
        RETURNS BOOLEAN
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
        AS $$ SELECT EXISTS (SELECT 1 FROM users) $$;

        CREATE OR REPLACE FUNCTION spoonfuls_consume_invite(invite_hash TEXT)
        RETURNS BOOLEAN
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
        AS $$
        BEGIN
            UPDATE invites
            SET used_at = now()
            WHERE code_hash = invite_hash
              AND used_at IS NULL
              AND expires_at > now();
            RETURN FOUND;
        END;
        $$;

        REVOKE ALL ON FUNCTION lookup_user_for_login(TEXT) FROM PUBLIC;
        REVOKE ALL ON FUNCTION spoonfuls_has_users() FROM PUBLIC;
        REVOKE ALL ON FUNCTION spoonfuls_consume_invite(TEXT) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION lookup_user_for_login(TEXT) TO spoonfuls_app;
        GRANT EXECUTE ON FUNCTION spoonfuls_has_users() TO spoonfuls_app;
        GRANT EXECUTE ON FUNCTION spoonfuls_consume_invite(TEXT) TO spoonfuls_app;
        """,
    ),
]


def database_url() -> str:
    """Return the configured PostgreSQL URL without embedding a secret in code."""

    return os.environ.get("DATABASE_URL", "postgresql://spoonfuls@localhost:5432/spoonfuls")


def migration_database_url() -> str:
    """Return the owner URL used only while applying migrations."""

    return os.environ.get("MIGRATION_DATABASE_URL", database_url())


@contextmanager
def connection(url: str | None = None) -> Iterator[psycopg.Connection]:
    """Yield a short-lived connection and close it on exit."""

    with psycopg.connect(url or database_url()) as conn:
        yield conn


def _ensure_app_role(conn: psycopg.Connection) -> None:
    """Create the least-privileged runtime role before granting table access."""

    password = os.environ.get("SPOONFULS_APP_PASSWORD")
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        if cur.fetchone() is None:
            if password:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT PASSWORD {}"
                    ).format(sql.Identifier(APP_ROLE), sql.Literal(password))
                )
            else:
                # Local migrations still need the role named by default grants;
                # the runtime startup guard refuses the owner connection later.
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT"
                    ).format(sql.Identifier(APP_ROLE))
                )
        elif password:
            cur.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(APP_ROLE), sql.Literal(password)
                )
            )


def _grant_app_role(conn: psycopg.Connection) -> None:
    """Grant only runtime table access when the separate role is configured."""

    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        if cur.fetchone() is not None:
            role = sql.Identifier(APP_ROLE)
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
            cur.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, invites TO {}"
                )
                .format(role)
            )
            cur.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION lookup_user_for_login(TEXT), "
                        "spoonfuls_has_users(), spoonfuls_consume_invite(TEXT) TO {}")
                .format(role)
            )


def apply_migrations() -> None:
    """Apply each numbered migration once, in order."""

    with connection(migration_database_url()) as conn:
        _ensure_app_role(conn)
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
            for version, name, migration_sql in MIGRATIONS:
                if version in applied:
                    continue
                cur.execute(migration_sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                    (version, name),
                )
            _grant_app_role(conn)


def is_ready() -> bool:
    """Check that PostgreSQL accepts a connection."""

    try:
        with connection() as conn:
            conn.execute("SELECT 1")
        return True
    except (OSError, psycopg.Error):
        return False


def runtime_role_is_safe() -> bool:
    """Return whether the runtime connection cannot bypass row-level security."""

    try:
        with connection() as conn:
            row = conn.execute(
                "SELECT NOT (rolsuper OR rolbypassrls) "
                "FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
        return bool(row and row[0])
    except (OSError, psycopg.Error):
        return False
