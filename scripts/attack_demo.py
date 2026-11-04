# attack_demo.py
# Демонстрация «до / после»: поднимает рядом уязвимую версию сервиса
# (первый коммит git) и исправленную (текущий код) и выполняет против
# обеих одни и те же атаки. Результат — таблица в консоли.
#   уязвимая версия    — http://127.0.0.1:8001
#   исправленная версия — http://127.0.0.1:8002
# Запуск: python scripts/attack_demo.py            (атаки и выход)
#         python scripts/attack_demo.py --keep     (серверы остаются для Swagger)

import os
import pathlib
import secrets
import subprocess
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PY = str(VENV_PY if VENV_PY.exists() else sys.executable)
if pathlib.Path(sys.executable).resolve() != pathlib.Path(PY).resolve():
    sys.exit(subprocess.call([PY, __file__, *sys.argv[1:]]))

import jwt  # noqa: E402
import requests  # noqa: E402

VULN, FIXED = "http://127.0.0.1:8001", "http://127.0.0.1:8002"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def vulnerable_copy(tmp):
    """Выгружает пакет app из первого коммита (уязвимая версия)."""
    base = git("rev-list", "--max-parents=0", "HEAD").decode().strip()
    dst = pathlib.Path(tmp) / "vulnerable"
    for path in git("ls-tree", "-r", "--name-only", base, "app").decode().split():
        target = dst / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git("show", f"{base}:{path}"))
    return dst, base[:7]


def start(cwd, port, db):
    env = {**os.environ, "RBAC_DB": db, "PYTHONUTF8": "1",
           "JWT_SECRET": secrets.token_urlsafe(48)}
    proc = subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--port", str(port),
                             "--log-level", "warning"], cwd=cwd, env=env)
    for _ in range(60):
        try:
            requests.get(f"http://127.0.0.1:{port}/docs", timeout=1)
            return proc
        except requests.ConnectionError:
            time.sleep(0.2)
    raise RuntimeError(f"сервер на порту {port} не запустился")


def login(base, username, password):
    r = requests.post(f"{base}/api/v1/auth/login",
                      json={"username": username, "password": password}, timeout=5)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def short(r):
    try:
        body = r.json()
    except ValueError:
        body = r.text
    text = str(body if not isinstance(body, dict) else body.get("detail", body.get("result", body)))
    text = " | ".join(part.strip() for part in text.splitlines() if part.strip())
    return f"{r.status_code} {text}"[:80]


def attacks(base):
    user = login(base, "user", "User#2026")
    forged = {"Authorization": "Bearer " + jwt.encode(
        {"sub": "1", "name": "admin"}, "attacker-key-0123456789abcdef0123", algorithm="HS256")}
    sqli = requests.get(f"{base}/api/v1/users/search", params={"q": "zzz' OR 1=1 --"},
                        headers=user, timeout=5)
    leaked = [u["username"] for u in sqli.json()] if sqli.ok else []
    return [
        ("SQL-инъекция: q = zzz' OR 1=1 --",
         f"{sqli.status_code} найдено: {leaked or 'никого'}"),
        ("Поддельный JWT (чужой ключ) → создать ADMIN",
         short(requests.post(f"{base}/api/v1/admin/users", headers=forged, timeout=5,
                             json={"username": "hacker", "password": "Hacker#2026",
                                   "role": "ADMIN"}))),
        ("USER → экспорт аудита + инъекция команды «whoami»",
         short(requests.get(f"{base}/api/v1/moderator/audit/export", headers=user,
                            params={"fmt": "csv & whoami"}, timeout=10))),
        ("USER → журнал аудита (нет права VIEW_AUDIT)",
         short(requests.get(f"{base}/api/v1/moderator/audit", headers=user, timeout=5))),
    ]


with tempfile.TemporaryDirectory() as tmp:
    vuln_dir, base = vulnerable_copy(tmp)
    servers = [start(vuln_dir, 8001, os.path.join(tmp, "vuln.db")),
               start(ROOT, 8002, os.path.join(tmp, "fixed.db"))]
    try:
        before, after = attacks(VULN), attacks(FIXED)
        print(f"\nУязвимая версия (коммит {base}) — {VULN}")
        print(f"Исправленная версия (текущий код) — {FIXED}\n")
        for (name, b), (_, a) in zip(before, after):
            print(f"■ {name}\n   уязвимая:     {b}\n   исправленная: {a}\n")
        if "--keep" in sys.argv:
            print("Серверы работают: Swagger — http://127.0.0.1:8001/docs и "
                  "http://127.0.0.1:8002/docs. Остановить — Ctrl+C.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for s in servers:
            s.terminate()
            s.wait()
