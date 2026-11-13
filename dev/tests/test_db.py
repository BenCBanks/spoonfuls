import os
from uuid import uuid4

import psycopg
import pytest

from app import db


pytestmark = pytest.mark.skipif(
    not os.environ.get("MIGRATION_DATABASE_URL"),
    reason="database integration checks run in CI's PostgreSQL service",
)


def _owner_connection():
    return psycopg.connect(db.migration_database_url())


def _set_user(conn, user_id):
    conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))


def test_migrations_are_idempotent_and_runtime_role_is_restricted():
    db.apply_migrations()
    db.apply_migrations()
    with _owner_connection() as conn:
        migration_count = conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE version = 1"
        ).fetchone()[0]
        role = conn.execute(
            "SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = %s",
            (db.APP_ROLE,),
        ).fetchone()
    assert migration_count == 1
    assert role == (False, False)


def test_runtime_role_cannot_read_or_update_another_users_rows():
    user_a, user_b = uuid4(), uuid4()
    session_a, session_b = uuid4(), uuid4()
    with _owner_connection() as conn:
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM users")
        conn.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s), (%s, %s, %s)",
            (user_a, "a@example.test", "hash-a", user_b, "b@example.test", "hash-b"),
        )
        conn.execute(
            "INSERT INTO sessions (id, user_id, token_hash, expires_at) "
            "VALUES (%s, %s, %s, now() + interval '1 day'), (%s, %s, %s, now() + interval '1 day')",
            (session_a, user_a, "token-a", session_b, user_b, "token-b"),
        )

    with db.connection() as conn:
        _set_user(conn, user_a)
        assert conn.execute("SELECT id FROM users ORDER BY id").fetchall() == [(user_a,)]
        assert conn.execute("SELECT user_id FROM sessions").fetchall() == [(user_a,)]
        assert conn.execute(
            "UPDATE users SET password_hash = 'changed' WHERE id = %s", (user_b,)
        ).rowcount == 0
        assert conn.execute(
            "UPDATE sessions SET token_hash = 'changed' WHERE id = %s", (session_b,)
        ).rowcount == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE users SET is_admin = true WHERE id = %s", (user_a,))
        conn.rollback()


def test_email_index_is_case_insensitive():
    with _owner_connection() as conn:
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s), (%s, %s)",
                ("Case@example.test", "hash-1", "case@example.test", "hash-2"),
            )
        conn.rollback()
