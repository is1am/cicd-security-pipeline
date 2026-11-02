# db.py
# SQLite-база RBAC из ПР5: users, roles, permissions, user_roles, role_permissions.

import os
import sqlite3

from app.security import hash_password

DB_PATH = os.environ.get("RBAC_DB", "rbac.db")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);
CREATE TABLE IF NOT EXISTS permissions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    resource TEXT NOT NULL,
    action   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
"""

ROLES = {
    "ADMIN": ["READ_PUBLIC", "VIEW_AUDIT", "MANAGE_USERS", "EXPORT_AUDIT"],
    "MODERATOR": ["READ_PUBLIC", "VIEW_AUDIT"],
    "USER": ["READ_PUBLIC"],
}
PERMISSIONS = {
    "READ_PUBLIC": ("public", "read"),
    "VIEW_AUDIT": ("audit", "read"),
    "EXPORT_AUDIT": ("audit", "export"),
    "MANAGE_USERS": ("users", "write"),
}
SEED_USERS = [("admin", "Admin#2026", "ADMIN"),
              ("moder", "Moder#2026", "MODERATOR"),
              ("user", "User#2026", "USER")]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        for name, (res, act) in PERMISSIONS.items():
            conn.execute("INSERT INTO permissions(name, resource, action) VALUES (?, ?, ?)",
                         (name, res, act))
        for role, perms in ROLES.items():
            rid = conn.execute("INSERT INTO roles(name) VALUES (?)", (role,)).lastrowid
            for p in perms:
                conn.execute("INSERT INTO role_permissions SELECT ?, id FROM permissions "
                             "WHERE name = ?", (rid, p))
        for username, password, role in SEED_USERS:
            create_user(conn, username, password, role)


def create_user(conn, username, password, role):
    uid = conn.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)",
                       (username, hash_password(password))).lastrowid
    conn.execute("INSERT INTO user_roles SELECT ?, id FROM roles WHERE name = ?", (uid, role))
    return uid


def get_permissions(conn, user_id):
    rows = conn.execute(
        "SELECT DISTINCT p.name FROM permissions p "
        "JOIN role_permissions rp ON rp.permission_id = p.id "
        "JOIN user_roles ur ON ur.role_id = rp.role_id WHERE ur.user_id = ?",
        (user_id,)).fetchall()
    return {r["name"] for r in rows}
