# security.py
# Хеширование паролей и JWT (исправленная версия по результатам SAST).

import datetime
import hashlib
import hmac
import os
import secrets

import jwt

SIGNING_KEY = os.environ.get("JWT_SECRET", "")  # секрет только из окружения / Vault
ALGORITHM = "HS256"
PBKDF2_ITERATIONS = 600_000                      # рекомендация OWASP для PBKDF2-SHA256

if len(SIGNING_KEY) < 32:
    raise RuntimeError("Переменная окружения JWT_SECRET не задана или короче 32 символов")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    _, iterations, salt, digest = password_hash.split("$")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                    int(iterations))
    return hmac.compare_digest(candidate.hex(), digest)


def create_token(user_id: int, username: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"sub": str(user_id), "name": username, "iat": now,
               "exp": now + datetime.timedelta(minutes=15)}
    return jwt.encode(payload, SIGNING_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    # подпись и срок действия проверяются, алгоритм — из белого списка
    return jwt.decode(token, SIGNING_KEY, algorithms=[ALGORITHM],
                      options={"require": ["sub", "exp"]})
