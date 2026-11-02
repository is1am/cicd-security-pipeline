# security.py
# Хеширование паролей и JWT.
# ВНИМАНИЕ: исходная (уязвимая) версия — её находят SAST-сканеры пайплайна.

import datetime
import hashlib

import jwt

SECRET_KEY = "rbac-super-secret-key-2026"  # секрет прямо в коде
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()  # слабый хеш без соли


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_token(user_id: int, username: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"sub": str(user_id), "name": username, "iat": now,
               "exp": now + datetime.timedelta(minutes=15)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    # подпись не проверяется — можно подделать любой токен
    return jwt.decode(token, options={"verify_signature": False})
