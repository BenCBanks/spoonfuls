import hashlib
import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app


pytestmark = pytest.mark.skipif(
    not os.environ.get("MIGRATION_DATABASE_URL"),
    reason="account integration checks run with CI's PostgreSQL service",
)


def owner_connection():
    return psycopg.connect(db.migration_database_url())


@pytest.fixture(autouse=True)
def clean_database(monkeypatch):
    db.apply_migrations()
    monkeypatch.setenv("SPOONFULS_COOKIE_SECURE", "0")
    with owner_connection() as conn:
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM invites")
        conn.execute("DELETE FROM users")
    yield


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies[auth.CSRF_COOKIE]}


def signup(client: TestClient, email: str, password: str, invite_code: str | None = None):
    body = {"email": email, "password": password}
    if invite_code:
        body["invite_code"] = invite_code
    return client.post("/api/auth/signup", json=body)


def test_first_account_is_admin_and_signs_in_with_secure_session_shape():
    with TestClient(app) as client:
        response = signup(client, "Admin@example.test", "a-long-fictional-password")
        assert response.status_code == 201
        assert response.json()["is_admin"] is True
        assert client.get("/api/auth/me").json()["email"] == "admin@example.test"

        signout = client.post("/api/auth/signout", headers=csrf_headers(client))
        assert signout.status_code == 204

    response = TestClient(app).post(
        "/api/auth/signin",
        json={"email": "admin@example.test", "password": "a-long-fictional-password"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_invites_are_single_use_and_expiry_is_enforced():
    with TestClient(app) as admin:
        assert signup(admin, "admin@example.test", "a-long-fictional-password").status_code == 201
        invite_response = admin.post("/api/auth/invites", json={}, headers=csrf_headers(admin))
        assert invite_response.status_code == 201
        invite_code = invite_response.json()["code"]

    with TestClient(app) as invited:
        response = signup(invited, "guest@example.test", "another-long-password", invite_code)
        assert response.status_code == 201
        assert response.json()["is_admin"] is False

    with TestClient(app) as reused:
        response = signup(reused, "third@example.test", "third-long-password", invite_code)
        assert response.status_code == 400
        assert response.json()["detail"]["field"] == "invite_code"

    expired_code = "expired-fictional-code"
    with owner_connection() as conn:
        admin_id = conn.execute(
            "SELECT id FROM users WHERE email = 'admin@example.test'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO invites (code_hash, created_by, expires_at) VALUES (%s, %s, %s)",
            (hashlib.sha256(expired_code.encode()).hexdigest(), admin_id, datetime.now(timezone.utc) - timedelta(days=1)),
        )
    with TestClient(app) as expired:
        response = signup(expired, "expired@example.test", "expired-long-password", expired_code)
        assert response.status_code == 400


def test_wrong_password_is_generic_and_rate_limited():
    email = "rate-limit@example.test"
    with TestClient(app) as client:
        assert signup(client, email, "a-long-fictional-password").status_code == 201
    for _ in range(auth.LOGIN_FAILURE_LIMIT):
        response = TestClient(app).post(
            "/api/auth/signin", json={"email": email, "password": "wrong-password"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Email or password is incorrect."
    limited = TestClient(app).post(
        "/api/auth/signin", json={"email": email, "password": "wrong-password"}
    )
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_expired_session_is_rejected_and_writes_need_csrf():
    with TestClient(app) as client:
        assert signup(client, "session@example.test", "a-long-fictional-password").status_code == 201
        without_csrf = client.post("/api/auth/signout")
        assert without_csrf.status_code == 403
        with owner_connection() as conn:
            conn.execute("UPDATE sessions SET expires_at = now() - interval '1 second'")
        assert client.get("/api/auth/me").status_code == 401
