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

Создайте репозиторий, выполните push, затем включите обязательную проверку
`Security Gate` в Settings → Branches → Branch protection rules.
