# main.py
# RBAC-сервис из ПР5 (FastAPI). Объект проверки для SAST/SCA-пайплайна.
# Исправленная версия по результатам SAST/SCA.

import csv
import io
import os
import sqlite3
from typing import Literal

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app import db
from app.security import create_token, decode_token, verify_password

app = FastAPI(title="RBAC Service", version="1.0")
db.init_db()


class LoginIn(BaseModel):
    username: str
    password: str


Role = Literal["USER", "MODERATOR", "ADMIN"]  # неизвестная роль -> 422


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    role: Role = "USER"


class RoleIn(BaseModel):
    role: Role


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется токен")
    try:
        claims = decode_token(authorization[7:])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен")
    with db.connect() as conn:
        row = conn.execute("SELECT is_active FROM users WHERE id = ?",
                           (int(claims["sub"]),)).fetchone()
    if not row or not row["is_active"]:  # удалённый или заблокированный пользователь
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Учётная запись неактивна")
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
        # параметризованный запрос: значение передаётся отдельно от SQL
        rows = conn.execute("SELECT id, username FROM users WHERE username LIKE ?",
                            (f"%{q}%",)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/moderator/audit")
def audit(user=Depends(require_permission("VIEW_AUDIT"))):
    return {"events": ["login admin", "login moder"]}


@app.get("/api/v1/moderator/audit/export")
def audit_export(user=Depends(require_permission("EXPORT_AUDIT"))):
    # экспорт формируется средствами Python, без вызова командной оболочки
    buf = io.StringIO()
    csv.writer(buf).writerows([["event"], ["login admin"], ["login moder"]])
    return {"result": buf.getvalue()}


@app.get("/api/v1/admin/users")
def list_users(user=Depends(require_permission("MANAGE_USERS"))):
    with db.connect() as conn:
        return db.list_users(conn)


@app.post("/api/v1/admin/users", status_code=201)
def create_user(body: UserIn, user=Depends(require_permission("MANAGE_USERS"))):
    try:
        with db.connect() as conn:
            uid = db.create_user(conn, body.username, body.password, body.role)
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь уже существует")
    return {"id": uid, "username": body.username, "role": body.role}


@app.put("/api/v1/admin/users/{user_id}/role")
def change_role(user_id: int, body: RoleIn, user=Depends(require_permission("MANAGE_USERS"))):
    with db.connect() as conn:
        if not db.set_role(conn, user_id, body.role):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    return {"id": user_id, "role": body.role}


@app.post("/api/v1/admin/import")
def import_users(payload: str, user=Depends(require_permission("MANAGE_USERS"))):
    data = yaml.safe_load(payload)  # только базовые типы YAML, без создания объектов
    return {"imported": len(data or [])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", 8000)))
