# main.py
# RBAC-сервис из ПР5 (FastAPI). Объект проверки для SAST/SCA-пайплайна.
# ВНИМАНИЕ: исходная (уязвимая) версия.

import os
import subprocess

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from app import db
from app.security import create_token, decode_token, verify_password

app = FastAPI(title="RBAC Service", version="1.0")
db.init_db()


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "USER"


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется токен")
    try:
        claims = decode_token(authorization[7:])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен")
    return {"id": int(claims["sub"]), "username": claims["name"]}


def require_permission(required: str):
    def dependency(user=Depends(get_current_user)):
        with db.connect() as conn:
            if required not in db.get_permissions(conn, user["id"]):
                raise HTTPException(status.HTTP_403_FORBIDDEN,
                                    "Недостаточно прав для выполнения операции")
        return user
    return dependency


@app.post("/api/v1/auth/login")
def login(body: LoginIn):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?",
                           (body.username,)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    return {"access_token": create_token(row["id"], row["username"]), "token_type": "bearer"}


@app.get("/api/v1/public")
def public(user=Depends(require_permission("READ_PUBLIC"))):
    return {"message": f"Привет, {user['username']}"}


@app.get("/api/v1/users/search")
def search_users(q: str, user=Depends(require_permission("READ_PUBLIC"))):
    with db.connect() as conn:
        # SQL-инъекция: параметр подставляется в строку запроса
        rows = conn.execute(
            f"SELECT id, username FROM users WHERE username LIKE '%{q}%'").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/moderator/audit")
def audit(user=Depends(require_permission("VIEW_AUDIT"))):
    return {"events": ["login admin", "login moder"]}


@app.get("/api/v1/moderator/audit/export")
def audit_export(fmt: str = "csv", user=Depends(get_current_user)):
    # нет проверки разрешения EXPORT_AUDIT + инъекция команд ОС
    out = subprocess.check_output(f"echo audit export as {fmt}", shell=True)
    return {"result": out.decode().strip()}


@app.post("/api/v1/admin/users", status_code=201)
def create_user(body: UserIn, user=Depends(require_permission("MANAGE_USERS"))):
    with db.connect() as conn:
        uid = db.create_user(conn, body.username, body.password, body.role)
    return {"id": uid, "username": body.username, "role": body.role}


@app.post("/api/v1/admin/import")
def import_users(payload: str, user=Depends(require_permission("MANAGE_USERS"))):
    data = yaml.load(payload, Loader=yaml.Loader)  # небезопасная десериализация
    return {"imported": len(data or [])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
