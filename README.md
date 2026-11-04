# ПР5 — CI/CD Security Pipeline (SAST + SCA)

RBAC-сервис на FastAPI и пайплайн безопасности для GitHub Actions и GitLab CI.

- `.github/workflows/security.yml`: Bandit, Semgrep, pip-audit, Trivy, Gitleaks, pytest, Security Gate
- `.gitlab-ci.yml`: те же проверки для GitLab
- `.semgrep/rbac-rules.yml`: собственные правила (маршрут без require_permission, JWT без проверки подписи, секрет в коде)
- `security-policy.json` + `scripts/security_gate.py`: политика блокировки

История git: первый коммит содержит уязвимую версию, второй — исправления.

## Локальный запуск

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt bandit semgrep pip-audit python-docx pillow
.venv\Scripts\python scripts\run_local_scans.py after
.venv\Scripts\python scripts\make_screenshots.py
.venv\Scripts\python build_report.py
```

## Запуск в GitHub

Репозиторий: https://github.com/is1am/cicd-security-pipeline

Создайте репозиторий, выполните push, затем включите обязательную проверку
`Security Gate` в Settings → Branches → Branch protection rules.

## RBAC: схема БД и тесты API

- `sql/rbac_schema.sql`: схема для PostgreSQL (FOREIGN KEY, ON DELETE CASCADE) и начальные данные
- `postman/RBAC_PR5.postman_collection.json` и `RBAC_PR5.postman_environment.json`: 21 запрос (позитивные, негативные, смена роли «на лету»)

Ручной прогон в Postman: запустите сервис

```
$env:JWT_SECRET="local-demo-secret-0123456789abcdef0123456789"; .venv\Scripts\python -m uvicorn app.main:app --port 8000
```

импортируйте оба JSON-файла, выберите окружение «ПР5 RBAC local» и запустите коллекцию (Run collection).
Автоматический прогон тех же запросов: `.venv\Scripts\python scripts\run_collection.py`.
