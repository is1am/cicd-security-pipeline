# make_screenshots.py
# Строит HTML-страницы из реальных результатов прогонов (reports/before, reports/after)
# и снимает их headless-браузером Edge в PNG (папка screenshots/).

import html
import json
import pathlib
import re
import sys
import subprocess
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

CSS = """
body{margin:0;background:#1e1f22;font-family:Segoe UI,Arial,sans-serif;color:#ddd;padding:24px}
h1{font-size:19px;margin:0 0 14px;color:#fff}
.term{background:#0c0c0c;border:1px solid #3c3f45;border-radius:8px;overflow:hidden}
.bar{background:#2b2d31;padding:7px 12px;font-size:13px;color:#aaa;border-bottom:1px solid #3c3f45}
pre{margin:0;padding:12px 14px;font:13px/1.45 Consolas,monospace;color:#ccc;white-space:pre-wrap;word-break:break-word}
.p{color:#6bdd9a}.r{color:#ff6b6b}.y{color:#ffd166}.g{color:#7bd88f}.c{color:#7cc4ff}.d{color:#888}
table{border-collapse:collapse;width:100%;font-size:13px;background:#2b2d31}
th,td{border:1px solid #3c3f45;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#25272b;color:#fff}
td code{font-family:Consolas,monospace;color:#7cc4ff}
.ok{color:#7bd88f;font-weight:700}.bad{color:#ff6b6b;font-weight:700}
.ERROR,.HIGH,.CRITICAL{color:#ff6b6b;font-weight:700}.WARNING,.MEDIUM{color:#ffd166;font-weight:700}
.LOW{color:#9aa0a6}
.res{margin-top:14px;font-size:16px}
"""


def page(title, body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>'
            f'<body><h1>{html.escape(title)}</h1>{body}</body></html>')


def shoot(name, content, width=1200):
    # Edge не сохраняет скриншот по пути с кириллицей — рендерим во временную папку
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "page.html"
        src.write_text(content, encoding="utf-8")
        shot = pathlib.Path(tmp) / "shot.png"
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--screenshot={shot}", f"--window-size={width},4000",
                        "--force-device-scale-factor=1", src.as_uri()],
                       check=True, capture_output=True, timeout=90)
        im = Image.open(shot).convert("RGB")
    bg = im.getpixel((5, im.height - 5))
    px = im.load()
    bottom = im.height
    for y in range(im.height - 1, 0, -1):
        if any(px[x, y] != bg for x in range(0, im.width, 3)):
            bottom = y + 24
            break
    im.crop((0, 0, im.width, min(bottom, im.height))).save(OUT / f"{name}.png")
    print("saved", name, im.width, "x", bottom)


def step(label, title):
    """Блок одного шага из console.log: команда и вывод."""
    log = (ROOT / "reports" / label / "console.log").read_text(encoding="utf-8")
    for block in log.split("\n$ ")[0:]:
        block = block.lstrip("$ ")
        if f"[{title}]" in block:
            return block
    raise KeyError(title)


def colorize(text):
    t = html.escape(text)
    t = re.sub(r"^(.+)$", r'<span class="p">$ \1</span>', t, count=1, flags=re.M)
    for word, cls in [("FAILED", "r"), ("PASSED", "g"), ("ERROR", "r"), ("High", "r"),
                      ("Medium", "y"), ("Low", "d"), ("passed", "g"), ("failed", "r")]:
        t = re.sub(rf"\b{word}\b", f'<span class="{cls}">{word}</span>', t)
    t = re.sub(r"(\[[^\]]+\] exit=\d+ time=[\d.]+s)", r'<span class="c">\1</span>', t)
    return t


def terminal(name, title, text, bar="PowerShell — ПР5_CICD_Security"):
    shoot(name, page(title, f'<div class="term"><div class="bar">{html.escape(bar)}</div>'
                            f'<pre>{colorize(text)}</pre></div>'))


def trim_pytest(text):
    keep = [ln for ln in text.splitlines()
            if not re.search(r"(Warning|warnings|from starlette|return self\._jws|Docs:|^\s*$|"
                             r"site-packages|^tests/test_rbac.py::\w+$)", ln)]
    return "\n".join(keep)


def trim_bandit(text):
    keep = [ln for ln in text.splitlines()
            if not re.search(r"(More Info|^\s*$|^\s*\d+\s|----)", ln)]
    i = next(i for i, ln in enumerate(keep) if "Code scanned" in ln)
    return "\n".join(keep[:i])


def trim_audit(text):
    lines = text.splitlines()
    out, seen = [], set()
    for ln in lines:
        key = ln.split()[:3] if ln and ln[0].isalpha() else None
        if key and tuple(key) in seen:
            continue
        if key:
            seen.add(tuple(key))
        out.append(ln)
    return "\n".join(out)


def semgrep_table(label):
    data = json.loads((ROOT / "reports" / label / "semgrep.json").read_text(encoding="utf-8"))
    rows = "".join(
        f"<tr><td><code>{html.escape(r['path'].replace(chr(92), '/'))}:{r['start']['line']}</code></td>"
        f"<td>{html.escape(r['check_id'].split('.')[-1])}</td>"
        f"<td class='{r['extra']['severity']}'>{r['extra']['severity']}</td>"
        f"<td>{html.escape(r['extra'].get('metadata', {}).get('cwe', [''])[0] if isinstance(r['extra'].get('metadata', {}).get('cwe'), list) else r['extra'].get('metadata', {}).get('cwe', ''))}</td></tr>"
        for r in data["results"])
    head = ("<tr><th>Файл:строка</th><th>Правило</th><th>Уровень</th><th>CWE</th></tr>")
    note = (f"<p class='res'>Найдено: <b>{len(data['results'])}</b> · проверено файлов: "
            f"{len(data['paths']['scanned'])} · наборы: p/python, p/owasp-top-ten, "
            f".semgrep/rbac-rules.yml</p>")
    shoot(f"semgrep_{label}", page(f"Semgrep: результаты сканирования (semgrep.json, {label})",
                                   f"<table>{head}{rows}</table>{note}"))


def gate(label):
    data = json.loads((ROOT / "reports" / label / "gate.json").read_text(encoding="utf-8"))
    tools = [("Bandit", "SAST"), ("Semgrep", "SAST"), ("pip-audit", "SCA"), ("Trivy", "SCA")]
    rows = "".join(
        f"<tr><td>{t}</td><td>{k}</td><td>{sum(f['tool'] == t for f in data['findings'])}</td>"
        f"<td>{sum(f['tool'] == t and f['blocking'] for f in data['findings'])}</td></tr>"
        for t, k in tools)
    res = ('<p class="res ok">Результат: ПРОЙДЕН ✅ (exit 0)</p>' if data["passed"]
           else '<p class="res bad">Результат: ЗАБЛОКИРОВАНО ❌ (exit 1)</p>')
    shoot(f"gate_{label}", page(f"Security Gate — сводка ({label})",
                                "<table><tr><th>Инструмент</th><th>Тип</th><th>Всего находок</th>"
                                f"<th>Блокирующих</th></tr>{rows}</table>{res}"), width=900)


def pipeline():
    css = """
    .flow{display:flex;gap:14px;align-items:stretch}
    .st{flex:1;background:#2b2d31;border:1px solid #3c3f45;border-radius:8px;padding:10px}
    .st h2{font-size:14px;margin:0 0 8px;color:#fff;text-transform:uppercase;letter-spacing:.5px}
    .job{background:#1e1f22;border-left:4px solid #7cc4ff;border-radius:4px;padding:7px 9px;
         margin-bottom:8px;font-size:13px}
    .job b{display:block;color:#fff}.job span{color:#9aa0a6;font-size:12px}
    .sast{border-color:#ffd166}.sca{border-color:#c792ea}.sec{border-color:#ff8a65}
    .gate{border-color:#7bd88f}.arrow{align-self:center;font-size:26px;color:#666}
    .legend{margin-top:12px;font-size:12px;color:#aaa}
    """
    def job(cls, name, desc):
        return f'<div class="job {cls}"><b>{name}</b><span>{desc}</span></div>'
    body = (
        '<div class="flow">'
        '<div class="st"><h2>Триггер</h2>'
        + job("", "push / pull_request", "в ветку main")
        + job("", "schedule", "еженедельно, пн 03:00 — новые CVE")
        + job("", "Dependabot", "PR с обновлениями pip и actions")
        + '</div><div class="arrow">→</div>'
        '<div class="st"><h2>Параллельные проверки</h2>'
        + job("sast", "SAST · Bandit", "AST-анализ Python → JSON + SARIF")
        + job("sast", "SAST · Semgrep", "p/python, p/owasp-top-ten + RBAC-правила")
        + job("sca", "SCA · pip-audit", "дерево зависимостей, база PyPI/OSV")
        + job("sca", "SCA · Trivy fs", "requirements.txt, база NVD/GHSA")
        + job("sec", "Secrets · Gitleaks", "вся история git")
        + job("", "Tests · pytest", "функциональные и негативные тесты RBAC")
        + '</div><div class="arrow">→</div>'
        '<div class="st"><h2>Решение</h2>'
        + job("gate", "Security Gate", "security_gate.py + security-policy.json → exit 0 / 1")
        + job("gate", "Code Scanning", "SARIF → вкладка Security / MR-виджет GitLab")
        + job("gate", "Branch protection", "merge запрещён, пока проверки не пройдены")
        + "</div></div>"
        '<p class="legend">Жёлтый — SAST, фиолетовый — SCA, оранжевый — секреты, '
        "зелёный — принятие решения. Одинаковая логика реализована в "
        ".github/workflows/security.yml и .gitlab-ci.yml.</p>")
    shoot("pipeline", page("Архитектура CI/CD Security Pipeline", f"<style>{css}</style>{body}"),
          width=1300)


if __name__ == "__main__" and "--rbac" not in sys.argv:
    pipeline()
    terminal("pytest_before", "Тесты RBAC на исходной версии (этап test)",
             trim_pytest(step("before", "Tests · pytest")))
    terminal("bandit_before", "Bandit: исходная версия", trim_bandit(step("before", "SAST · Bandit (вывод)")))
    semgrep_table("before")
    terminal("pip_audit_before", "pip-audit: исходная версия requirements.txt",
             trim_audit(step("before", "SCA · pip-audit (вывод)")))
    gate("before")
    terminal("pytest_after", "Тесты RBAC после исправлений",
             trim_pytest(step("after", "Tests · pytest")))
    terminal("scans_after", "Bandit и pip-audit после исправлений",
             trim_bandit(step("after", "SAST · Bandit (вывод)")) + "\n\n$ "
             + step("after", "SCA · pip-audit (вывод)"))
    gate("after")


# ---------------------------------------------------------------- RBAC (ПР5)
def er_diagram():
    def entity(x, y, name, cols, w=230):
        h = 34 + 26 * len(cols)
        out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#2b2d31" stroke="#7cc4ff"/>',
               f'<rect x="{x}" y="{y}" width="{w}" height="34" rx="6" fill="#1f4e79"/>',
               f'<text x="{x + w / 2}" y="{y + 23}" text-anchor="middle" class="t">{name}</text>']
        for i, (key, col, typ) in enumerate(cols):
            cy = y + 34 + 26 * i + 18
            color = "#ffd166" if key == "PK" else "#c792ea" if key == "FK" else "#9aa0a6"
            out.append(f'<text x="{x + 10}" y="{cy}" class="k" fill="{color}">{key}</text>')
            out.append(f'<text x="{x + 46}" y="{cy}" class="c">{col}</text>')
            out.append(f'<text x="{x + w - 10}" y="{cy}" text-anchor="end" class="ty">{typ}</text>')
        return "".join(out)

    def link(x1, y1, x2, y2, label):
        # «один» со стороны справочника, «много» (вилка) со стороны таблицы связи
        mx = (x1 + x2) / 2
        d = 1 if x2 > x1 else -1
        return (f'<path d="M{x1},{y1} H{mx} V{y2} H{x2}" fill="none" stroke="#aaa" stroke-width="1.6"/>'
                f'<line x1="{x1 + 8 * d}" y1="{y1 - 8}" x2="{x1 + 8 * d}" y2="{y1 + 8}" stroke="#aaa" stroke-width="1.6"/>'
                f'<line x1="{x2}" y1="{y2}" x2="{x2 - 12 * d}" y2="{y2 - 8}" stroke="#aaa" stroke-width="1.6"/>'
                f'<line x1="{x2}" y1="{y2}" x2="{x2 - 12 * d}" y2="{y2 + 8}" stroke="#aaa" stroke-width="1.6"/>'
                f'<text x="{mx - 10}" y="{max(y1, y2) + 18}" class="l">{label}</text>')

    users = [("PK", "id", "SERIAL"), ("", "username", "VARCHAR(50) UQ"),
             ("", "password_hash", "VARCHAR(255)"), ("", "is_active", "BOOLEAN")]
    ur = [("PK FK", "user_id", "INTEGER"), ("PK FK", "role_id", "INTEGER")]
    roles = [("PK", "id", "SERIAL"), ("", "name", "VARCHAR(50) UQ"), ("", "description", "TEXT")]
    rp = [("PK FK", "role_id", "INTEGER"), ("PK FK", "permission_id", "INTEGER")]
    perms = [("PK", "id", "SERIAL"), ("", "name", "VARCHAR(50) UQ"),
             ("", "resource", "VARCHAR(50)"), ("", "action", "VARCHAR(20)")]
    ur = [(k.replace("PK FK", "FK"), c, t) for k, c, t in ur]
    rp = [(k.replace("PK FK", "FK"), c, t) for k, c, t in rp]
    def row(y, i):  # вертикальный центр i-й строки сущности, начинающейся с y
        return y + 34 + 26 * i + 13

    Y = 90
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1390" height="330" style="background:#1e1f22">'
        '<style>.t{font:700 15px Segoe UI;fill:#fff}.c{font:14px Consolas;fill:#e6e6e6}'
        '.k{font:700 12px Consolas}.ty{font:12px Consolas;fill:#8a8f98}'
        '.l{font:12px Segoe UI;fill:#aaa}.n{font:12px Segoe UI;fill:#9aa0a6}</style>'
        + entity(20, Y, "users", users, 270)
        + entity(340, Y + 26, "user_roles", ur, 190)
        + entity(580, Y, "roles", roles, 230)
        + entity(860, Y + 26, "role_permissions", rp, 210)
        + entity(1120, Y, "permissions", perms, 250)
        + link(290, row(Y, 0), 340, row(Y + 26, 0), "1:N")
        + link(580, row(Y, 0), 530, row(Y + 26, 1), "1:N")
        + link(810, row(Y, 0), 860, row(Y + 26, 0), "1:N")
        + link(1120, row(Y, 0), 1070, row(Y + 26, 1), "1:N")
        + '<text x="20" y="290" class="n">PK — первичный ключ, FK — внешний ключ (ON DELETE CASCADE ON UPDATE CASCADE), '
          'UQ — уникальное значение. Первичные ключи таблиц связи составные: (user_id, role_id) и (role_id, permission_id).</text>'
        '<text x="20" y="312" class="n">Связи users ↔ roles и roles ↔ permissions — многие-ко-многим через таблицы user_roles и role_permissions.</text>'
        "</svg>")
    shoot("er_rbac", page("ER-диаграмма базы данных RBAC", svg), width=1440)


def api_cards(name, title, pick):
    data = json.loads((ROOT / "reports" / "api" / "results.json").read_text(encoding="utf-8"))
    css = """
    .card{background:#2b2d31;border:1px solid #3c3f45;border-radius:8px;margin-bottom:14px;overflow:hidden}
    .top{display:flex;gap:10px;align-items:center;padding:9px 14px;background:#25272b;border-bottom:1px solid #3c3f45}
    .m{font:700 14px Consolas}.GET{color:#6bdd9a}.POST{color:#ffb454}.PUT{color:#7cc4ff}
    .url{font:14px Consolas;color:#e6e6e6;flex:1}.nm{padding:8px 14px 0;color:#9aa0a6;font-size:13px}
    .sec{padding:4px 14px 8px;font:13px Consolas;white-space:pre-wrap;word-break:break-all;color:#ccc}
    .lbl{color:#8a8f98;font:12px Segoe UI;text-transform:uppercase;letter-spacing:.5px}
    .st{padding:3px 10px;border-radius:4px;font:700 13px Consolas}
    .s2{background:#1f5135;color:#7bd88f}.s4{background:#5c2526;color:#ff8a8a}
    .ok{color:#7bd88f;font:700 13px Segoe UI}.ms{color:#8a8f98;font:12px Consolas}
    """
    cards = []
    for r in data["results"]:
        if not pick(r):
            continue
        st_cls = "s2" if r["status"] < 300 else "s4"
        resp = r["response"]
        if isinstance(resp, dict) and "access_token" in resp:
            resp = {**resp, "access_token": resp["access_token"][:42] + "…"}
        body = (f'<div class="sec"><span class="lbl">Тело запроса</span>\n'
                f'{html.escape(json.dumps(r["body"], ensure_ascii=False, indent=2))}</div>' if r["body"] else "")
        auth = "Authorization: Bearer {{token}}" if r["auth"] else "без заголовка Authorization"
        cards.append(
            f'<div class="card"><div class="top"><span class="m {r["method"]}">{r["method"]}</span>'
            f'<span class="url">{html.escape(r["url"])}</span>'
            f'<span class="st {st_cls}">{r["status"]}</span><span class="ms">{r["ms"]} мс</span>'
            f'<span class="ok">{"✔ тест пройден" if r["passed"] else "✘ тест не пройден"}</span></div>'
            f'<div class="nm">{html.escape(r["name"])} · {html.escape(auth)} · ожидался {r["expected"]}</div>'
            f'{body}<div class="sec"><span class="lbl">Ответ</span>\n'
            f'{html.escape(json.dumps(resp, ensure_ascii=False, indent=2))}</div></div>')
    shoot(name, page(title, f"<style>{css}</style>" + "".join(cards)))


def rbac_screens():
    er_diagram()
    api_cards("api_t1", "Тест 1 (позитивный): ADMIN создаёт пользователя",
              lambda r: r["name"].startswith(("Вход ADMIN", "Т1.")))
    api_cards("api_t2", "Тест 2 (негативный): USER обращается к /api/v1/admin/users",
              lambda r: r["name"].startswith("Т2."))
    api_cards("api_neg", "Дополнительные негативные тесты: эскалация привилегий и подделка токена",
              lambda r: r["name"].startswith(("MODERATOR создаёт", "MODERATOR →", "Без токена",
                                              "Поддельный", "ADMIN: несуществующая")))
    api_cards("api_t3", "Тест 3: изменение роли «на лету» без перевыпуска токена",
              lambda r: r["name"].startswith("Т3."))
    log = (ROOT / "reports" / "api" / "console.log").read_text(encoding="utf-8")
    terminal("api_run", "Выполнение Postman-коллекции против запущенного сервиса",
             "python scripts/run_collection.py\n" + log)


if __name__ == "__main__" and "--rbac" in sys.argv:
    rbac_screens()
