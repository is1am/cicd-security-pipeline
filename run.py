# run.py
# Точка запуска сервиса для разработки: python run.py
# (из VS Code — кнопка Run на этом файле или конфигурация «RBAC Service» в Run and Debug).
# Если запуск идёт не из .venv, скрипт перезапускает себя интерпретатором .venv.
# Если JWT_SECRET не задан, генерируется случайный секрет на время работы сервера.

import os
import pathlib
import secrets
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

if VENV_PY.exists() and pathlib.Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    sys.exit(subprocess.call([str(VENV_PY), str(ROOT / "run.py"), *sys.argv[1:]]))

if not os.environ.get("JWT_SECRET"):
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
    print("JWT_SECRET не задан: сгенерирован временный секрет (токены действуют до перезапуска)")

os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

host = os.environ.get("HOST", "127.0.0.1")
port = int(os.environ.get("PORT", 8000))
print(f"Swagger UI: http://{host}:{port}/docs")
uvicorn.run("app.main:app", host=host, port=port)
