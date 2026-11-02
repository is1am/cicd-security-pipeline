# test_rbac.py
# Функциональные и негативные тесты RBAC (этап test пайплайна).

import os
import tempfile

os.environ["RBAC_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-0123456789")

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def token(username, password):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_creates_user():
    r = client.post("/api/v1/admin/users", headers=token("admin", "Admin#2026"),
                    json={"username": "new_user", "password": "N3w#pass", "role": "USER"})
    assert r.status_code == 201


def test_user_forbidden_on_admin():
    r = client.post("/api/v1/admin/users", headers=token("user", "User#2026"),
                    json={"username": "x", "password": "x"})
    assert r.status_code == 403


def test_user_cannot_export_audit():
    r = client.get("/api/v1/moderator/audit/export", headers=token("user", "User#2026"))
    assert r.status_code == 403


def test_forged_token_rejected():
    forged = jwt.encode({"sub": "1", "name": "admin"}, "attacker-key-0123456789abcdef0123",
                        algorithm="HS256")
    r = client.get("/api/v1/public", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_sql_injection_does_not_leak_users():
    r = client.get("/api/v1/users/search", params={"q": "zzz' OR 1=1 --"},
                   headers=token("user", "User#2026"))
    assert r.status_code == 200
    assert r.json() == []
