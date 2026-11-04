# run_collection.py
# Запускает сервис (uvicorn, чистая БД) и выполняет Postman-коллекцию
# postman/RBAC_PR5.postman_collection.json — упрощённый аналог Newman:
# подставляет {{переменные}}, проверяет ожидаемый статус из pm.test(...)
# и сохраняет переменные из pm.environment.set(...).
# Результат: reports/api/results.json и console.log.
# Запуск: python scripts/run_collection.py

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "api"
OUT.mkdir(parents=True, exist_ok=True)
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"

col = json.loads((ROOT / "postman/RBAC_PR5.postman_collection.json").read_text(encoding="utf-8"))
env = {"baseUrl": BASE}


def sub(text):
    text = text.replace("{{$timestamp}}", str(int(time.time())))
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(env.get(m.group(1), "")), text)


def start_server(db_path):
    e = {**os.environ, "RBAC_DB": db_path, "PORT": str(PORT), "PYTHONUTF8": "1",
         "JWT_SECRET": "local-demo-secret-0123456789abcdef0123456789"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT),
                             "--log-level", "warning"], cwd=ROOT, env=e)
    for _ in range(50):
        try:
            requests.get(BASE + "/docs", timeout=1)
            return proc
        except requests.ConnectionError:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("сервер не запустился")


def run():
    results, log = [], []
    for folder in col["item"]:
        for item in folder["item"]:
            req = item["request"]
            script = " ".join(item["event"][0]["script"]["exec"])
            expected = int(re.search(r"have\.status\((\d+)\)", script).group(1))
            headers = {h["key"]: sub(h["value"]) for h in req["header"]}
            body = sub(req["body"]["raw"]) if "body" in req else None
            url = sub(req["url"]["raw"])
            t0 = time.perf_counter()
            r = requests.request(req["method"], url, headers=headers,
                                 data=body.encode() if body else None, timeout=10)
            ms = (time.perf_counter() - t0) * 1000
            try:
                data = r.json()
            except ValueError:
                data = r.text
            for var, field in re.findall(r'pm\.environment\.set\("(\w+)", pm\.response\.json\(\)\.(\w+)\)', script):
                if isinstance(data, dict) and field in data:
                    env[var] = data[field]
            ok = r.status_code == expected
            results.append({"folder": folder["name"], "name": item["name"], "method": req["method"],
                            "url": url.replace(BASE, "{{baseUrl}}"), "auth": "Authorization" in headers,
                            "body": json.loads(body) if body else None, "status": r.status_code,
                            "expected": expected, "passed": ok, "ms": round(ms, 1),
                            "response": data, "at": time.time()})
            line = f"{'PASS' if ok else 'FAIL'}  {r.status_code} (ожидался {expected})  {ms:6.1f} мс  {req['method']:4} {item['name']}"
            print(line)
            log.append(line)
    return results, log


with tempfile.TemporaryDirectory() as tmp:
    server = start_server(os.path.join(tmp, "rbac.db"))
    try:
        results, log = run()
    finally:
        server.terminate()
        server.wait()

# Задержка применения новой роли: от ответа на PUT до первого успешного запроса тем же токеном
put = next(r for r in results if r["name"].startswith("Т3.2"))
after = next(r for r in results if r["name"].startswith("Т3.3"))
delay_ms = round((after["at"] - put["at"]) * 1000, 1)
summary = {"total": len(results), "passed": sum(r["passed"] for r in results),
           "role_change_delay_ms": delay_ms}
(OUT / "results.json").write_text(json.dumps({"summary": summary, "results": results},
                                             ensure_ascii=False, indent=2), encoding="utf-8")
log.append(f"\nИтого: {summary['passed']}/{summary['total']} проверок пройдено; "
           f"новая роль применилась через {delay_ms} мс после PUT (без перевыпуска токена)")
(OUT / "console.log").write_text("\n".join(log), encoding="utf-8")
print(log[-1])
sys.exit(0 if summary["passed"] == summary["total"] else 1)
