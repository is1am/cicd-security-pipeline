# run_local_scans.py
# Локально выполняет те же проверки, что и пайплайн (pytest, Bandit, Semgrep,
# pip-audit, Security Gate), и сохраняет отчёты в reports/<метка>/.
# Запуск: python scripts/run_local_scans.py before

import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = pathlib.Path(sys.executable).parent
label = sys.argv[1] if len(sys.argv) > 1 else "local"
OUT = ROOT / "reports" / label
OUT.mkdir(parents=True, exist_ok=True)
env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

STEPS = [
    ("Tests · pytest", [BIN / "pytest", "-v", "-p", "no:cacheprovider"]),
    ("SAST · Bandit", [BIN / "bandit", "-r", "app", "-f", "json", "-o", OUT / "bandit.json",
                       "--exit-zero"]),
    ("SAST · Bandit (вывод)", [BIN / "bandit", "-r", "app", "-q"]),
    ("SAST · Semgrep", [BIN / "semgrep", "scan", "--metrics=off", "--config", "p/python",
                        "--config", "p/owasp-top-ten", "--config", ".semgrep/rbac-rules.yml",
                        "--json", "-o", OUT / "semgrep.json", "app"]),
    ("SCA · pip-audit", [BIN / "pip-audit", "-r", "requirements.txt", "-f", "json",
                         "-o", OUT / "pip-audit.json"]),
    ("SCA · pip-audit (вывод)", [BIN / "pip-audit", "-r", "requirements.txt", "--desc", "off"]),
    ("Security Gate", [sys.executable, "scripts/security_gate.py", OUT, "--policy",
                       "security-policy.json", "--json", OUT / "gate.json"]),
]

log = []
for title, cmd in STEPS:
    t0 = time.time()
    p = subprocess.run([str(c) for c in cmd], cwd=ROOT, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    dt = time.time() - t0
    out = (p.stdout + p.stderr).strip()
    log.append(f"$ {' '.join(pathlib.Path(str(c)).name if i == 0 else str(c).replace(str(ROOT) + os.sep, '') for i, c in enumerate(cmd))}\n"
               f"{out}\n[{title}] exit={p.returncode} time={dt:.1f}s\n")
    print(f"{title:28} exit={p.returncode}  {dt:5.1f}s")

(OUT / "console.log").write_text("\n".join(log), encoding="utf-8")
