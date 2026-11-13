from hashlib import sha256

from fastapi.testclient import TestClient

from app.main import STATIC_DIR, app, db


def test_health_reports_database_state(monkeypatch):
    monkeypatch.setattr(db, "is_ready", lambda: True)
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "db": True}


def test_shell_and_security_headers(monkeypatch):
    monkeypatch.setattr(db, "is_ready", lambda: True)
    with TestClient(app) as client:
        response = client.get("/")
        static_response = client.get("/static/app.js")

    assert response.status_code == 200
    assert '<main id="app"' in response.text
    script_hash = sha256((STATIC_DIR / "app.js").read_bytes()).hexdigest()
    style_hash = sha256((STATIC_DIR / "style.css").read_bytes()).hexdigest()
    assert f"/static/app.js?v={script_hash}" in response.text
    assert f"/static/style.css?v={style_hash}" in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert static_response.headers["cache-control"].endswith("immutable")


def test_first_migration_has_private_users_and_sessions():
    from app.db import MIGRATIONS

    version, name, sql = MIGRATIONS[0]
    assert version == 1
    assert name == "users-and-sessions"
    assert "CREATE TABLE IF NOT EXISTS users" in sql
    assert "CREATE TABLE IF NOT EXISTS sessions" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
