# build_report.py
# Отчёт в формате Word (Отчет_ПР5.docx) по реальным результатам прогонов
# (reports/before, reports/after), скриншотам (screenshots/) и истории git.
# Запуск: .venv/Scripts/python build_report.py

import json
import pathlib
import re
import subprocess
from importlib.metadata import version

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "Отчет_ПР5.docx"

FONT = "Times New Roman"
MONO = "Consolas"

doc = Document()

# --- Страница и базовые стили (ГОСТ-подобно) -------------------------------
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin, sec.right_margin = Cm(3), Cm(1.5)
sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
sec.different_first_page_header_footer = True

normal = doc.styles["Normal"]
normal.font.name = FONT
normal.font.size = Pt(14)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
pf = normal.paragraph_format
pf.line_spacing = 1.5
pf.space_after = Pt(0)
pf.first_line_indent = Cm(1.25)
pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

for lvl, size in [(1, 16), (2, 14)]:
    st = doc.styles[f"Heading {lvl}"]
    st.font.name = FONT
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = RGBColor(0, 0, 0)
    rf = st.element.rPr.rFonts  # шрифт задаём явно, а не из темы

    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(attr), FONT)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(attr)) is not None:
            del rf.attrib[qn(attr)]
    hp = st.paragraph_format
    hp.space_before = Pt(12)
    hp.space_after = Pt(6)
    hp.first_line_indent = Cm(1.25)
    hp.keep_with_next = True
    hp.line_spacing = 1.15

# Номер страницы в нижнем колонтитуле (кроме титульного листа)
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
fp.paragraph_format.first_line_indent = Cm(0)
for tag, text in [("begin", None), (None, "PAGE"), ("end", None)]:
    run = fp.add_run()
    if tag:
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), tag)
    else:
        el = OxmlElement("w:instrText")
        el.set(qn("xml:space"), "preserve")
        el.text = text
    run._r.append(el)
    run.font.size = Pt(12)


# --- Вспомогательные функции ----------------------------------------------
def para(text="", bold=False, align=None, indent=True, size=None, italic=False, space_after=0):
    p = doc.add_paragraph()
    if text:
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
    if align is not None:
        p.alignment = align
    if not indent:
        p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_after = Pt(space_after)
    return p


def rich(parts):
    """Абзац из фрагментов: обычный текст или ('code', текст) / ('b', текст)."""
    p = doc.add_paragraph()
    for part in parts:
        if isinstance(part, tuple):
            kind, text = part
            r = p.add_run(text)
            if kind == "code":
                r.font.name = MONO
                r.font.size = Pt(12)
            elif kind == "b":
                r.bold = True
        else:
            p.add_run(part)
    return p


def bullets(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = Cm(1.9)
        p.paragraph_format.first_line_indent = Cm(-0.6)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        if isinstance(it, list):
            for part in it:
                if isinstance(part, tuple):
                    r = p.add_run(part[1])
                    if part[0] == "code":
                        r.font.name = MONO
                        r.font.size = Pt(12)
                    else:
                        r.bold = True
                else:
                    p.add_run(part)
        else:
            p.add_run(it)


def shade(el, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    el.append(shd)


def code(text):
    """Листинг: моноширинный шрифт, одинарный интервал, серый фон."""
    lines = text.strip("\n").split("\n")
    for i, line in enumerate(lines):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.line_spacing = 1.0
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.keep_with_next = i < len(lines) - 1
        if i == 0:
            pf.space_before = Pt(6)
        if i == len(lines) - 1:
            pf.space_after = Pt(6)
        r = p.add_run(line if line else " ")
        r.font.name = MONO
        r.font.size = Pt(9.5)
        r._r.rPr.rFonts.set(qn("w:hAnsi"), MONO)
        shade(p._p.get_or_add_pPr(), "F2F2F2")


fig_no = 0


def figure(png, caption, width_cm=16):
    global fig_no
    fig_no += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.line_spacing = 1.0
    p.add_run().add_picture(str(ROOT / png), width=Cm(width_cm))
    c = para(f"Рисунок {fig_no} — {caption}", align=WD_ALIGN_PARAGRAPH.CENTER,
             indent=False, size=12, space_after=6)
    c.paragraph_format.line_spacing = 1.0


tab_no = 0


def table(header, rows, widths_cm, caption):
    global tab_no
    tab_no += 1
    cp = para(f"Таблица {tab_no} — {caption}", indent=False, size=12)
    cp.paragraph_format.keep_with_next = True
    cp.paragraph_format.space_before = Pt(6)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False

    def fill(row, values, bold=False, bg=None):
        for cell, val, w in zip(row.cells, values, widths_cm):
            cell.width = Cm(w)
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(val))
            r.font.size = Pt(11)
            r.bold = bold
            if bg:
                shade(cell._tc.get_or_add_tcPr(), bg)

    for col, w in zip(t.columns, widths_cm):
        col.width = Cm(w)
    fill(t.rows[0], header, bold=True, bg="E7E6E6")
    # заголовок повторяется на новой странице
    trPr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)
    for row in rows:
        fill(t.add_row(), row)
    para("", space_after=0).paragraph_format.line_spacing = 1.0


def heading(text, level=1):
    return doc.add_heading(text, level=level)


def src(path, start=None, end=None):
    """Фрагмент исходного файла проекта по маркерам строк (включительно)."""
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    i = 0 if start is None else next(k for k, ln in enumerate(lines) if start in ln)
    j = len(lines) if end is None else next(k for k, ln in enumerate(lines) if k >= i and end in ln) + 1
    return "\n".join(lines[i:j])


def git_show(rev, path):
    return subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def snippet(text, start, end):
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if start in ln)
    j = next(k for k, ln in enumerate(lines) if k >= i and end in ln) + 1
    return "\n".join(lines[i:j])


api = json.loads((ROOT / "reports/api/results.json").read_text(encoding="utf-8"))
before = json.loads((ROOT / "reports/before/gate.json").read_text(encoding="utf-8"))
after = json.loads((ROOT / "reports/after/gate.json").read_text(encoding="utf-8"))


def count(data, tool, blocking=None):
    return sum(f["tool"] == tool and (blocking is None or f["blocking"] == blocking)
               for f in data["findings"])


BASE = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=ROOT,
                      capture_output=True, text=True, check=True).stdout.strip()
FIX = subprocess.run(["git", "log", "--format=%H", "--grep=Исправление уязвимостей"], cwd=ROOT,
                     capture_output=True, text=True, encoding="utf-8", check=True).stdout.split()[-1]
old_main, old_sec = git_show(BASE, "app/main.py"), git_show(BASE, "app/security.py")
old_req = git_show(BASE, "requirements.txt")

# --- Титульный лист --------------------------------------------------------
C = WD_ALIGN_PARAGRAPH.CENTER
para("МИНИСТЕРСТВО ОБРАЗОВАНИЯ И НАУКИ КАЗАХСТАН", bold=True, align=C, indent=False)
para("«НАО Евразийский национальный университет имени Л. Н. Гумилёва»", align=C, indent=False)
para("Факультет информационных технологий", align=C, indent=False)
para("Кафедра Информационная безопасность", align=C, indent=False)
for _ in range(4):
    para(indent=False)
para("ОТЧЕТ", bold=True, align=C, indent=False, size=18)
para("по практической работе № 5", bold=True, align=C, indent=False)
para(indent=False)
para("Дисциплина: «Клиент-серверные технологии и их безопасность»", align=C, indent=False)
para("Тема: «CI/CD Security Pipeline: настройка автоматического сканирования уязвимостей "
     "исходного кода (SAST) и зависимостей (SCA) в GitHub Actions / GitLab CI»",
     align=C, indent=False)
for _ in range(4):
    para(indent=False)
R = WD_ALIGN_PARAGRAPH.RIGHT
para("Руководитель, преподаватель _____________ Казиева Н.М.", align=R, indent=False)
para("«___» __________________ 2026", align=R, indent=False)
para(indent=False)
para("Выполнил магистрант группы МСИБ-24", align=R, indent=False)
para("Нуртазинов Ислам Тулегенович", align=R, indent=False)
para("«___» __________________ 2026", align=R, indent=False)
for _ in range(4):
    para(indent=False)
para("Астана, 2026", align=C, indent=False)

# --- 1. Цель ---------------------------------------------------------------
heading("1. Цель работы").paragraph_format.page_break_before = True
rich([("b", "Практическая: "),
      "построить конвейер CI/CD, который при каждом изменении кода автоматически выполняет "
      "статический анализ исходного кода (SAST), анализ состава программного обеспечения и "
      "уязвимостей зависимостей (SCA), поиск секретов и тесты, а затем по формальной политике "
      "решает, можно ли принимать изменение."])
rich([("b", "Теоретическая: "),
      "изучить подход DevSecOps и принцип «shift-left», классы уязвимостей, которые находят "
      "SAST и SCA, форматы обмена результатами (SARIF, отчёты GitLab) и ограничения "
      "автоматических сканеров; принципы проектирования ролевой модели доступа RBAC "
      "(NIST RBAC, принцип наименьших привилегий) и методы её негативного тестирования."])

# --- 2. Задание ------------------------------------------------------------
heading("2. Задание")
para("Вариант — тема № 46 из перечня мини-проектов: «CI/CD Security Pipeline: Настройка "
     "автоматического сканирования уязвимостей исходного кода (SAST) и зависимостей (SCA) "
     "в GitHub Actions / GitLab CI».")
para("Объектом проверки выбран REST-сервис с ролевой моделью доступа (RBAC) из методических "
     "указаний к практической работе № 5: таблицы users, roles, permissions, user_roles, "
     "role_permissions и эндпоинты /api/v1/public, /api/v1/moderator/audit, /api/v1/admin/users. "
     "Требуется:")
bullets([
    "подготовить исходную версию сервиса с типичными ошибками безопасности в коде и "
    "устаревшими зависимостями;",
    "описать пайплайн безопасности для GitHub Actions и для GitLab CI: SAST (Bandit, Semgrep), "
    "SCA (pip-audit, Trivy), поиск секретов (Gitleaks / Secret Detection), тесты;",
    "написать собственные правила SAST для проверки RBAC и единый Security Gate "
    "с политикой блокировки;",
    "выполнить сканирование, проанализировать находки, устранить уязвимости "
    "и показать, что после исправления пайплайн проходит.",
])
para("Дополнительно выполнены обязательные шаги методических указаний ПР5:")
bullets([
    "шаг 1 — SQL-скрипт таблиц users, roles, permissions, user_roles, role_permissions "
    "с FOREIGN KEY и ON DELETE CASCADE, ER-диаграмма;",
    "шаг 2 — middleware проверки разрешений и три уровня ресурсов: /api/v1/public, "
    "/api/v1/moderator/audit, /api/v1/admin/users;",
    "шаг 3 — позитивные и негативные тесты в Postman (200/201, 403), а также проверка "
    "смены роли «на лету» без перевыпуска токена.",
])

# --- 3. Теория -------------------------------------------------------------
heading("3. Теоретические сведения")
heading("3.1. DevSecOps и принцип «shift-left»", 2)
para("DevSecOps — практика встраивания проверок безопасности в каждый этап жизненного цикла "
     "разработки, а не в отдельный аудит перед выпуском. Принцип «shift-left» означает перенос "
     "проверок как можно ближе к моменту написания кода: уязвимость, найденная в pull request, "
     "исправляется за минуты, а найденная в эксплуатации — требует расследования инцидента, "
     "выпуска патча и уведомления пользователей. Пайплайн CI/CD — естественное место для таких "
     "проверок: он запускается при каждом изменении, одинаково для всех разработчиков, а его "
     "результат можно сделать обязательным условием слияния (branch protection).")

heading("3.2. SAST — статический анализ исходного кода", 2)
para("SAST (Static Application Security Testing) анализирует исходный код без его запуска: "
     "строит абстрактное синтаксическое дерево (AST), граф потока данных и ищет опасные "
     "конструкции — подстановку пользовательских данных в SQL-запрос или команду ОС, "
     "небезопасную десериализацию, слабые криптоалгоритмы, жёстко заданные секреты. "
     "Преимущества — полнота покрытия кода и точное указание файла и строки; недостатки — "
     "ложные срабатывания и слепота к ошибкам бизнес-логики, не описанным правилами "
     "(например, к забытой проверке роли). Последнее компенсируется собственными правилами.")
rich([("b", "Bandit"), " — анализатор Python от PyCQA: набор плагинов B1xx–B7xx по AST, "
      "у каждой находки есть уровень серьёзности (severity) и достоверности (confidence)."])
rich([("b", "Semgrep"), " — многоязычный анализатор с правилами в виде шаблонов кода "
      "(YAML). Поддерживает наборы правил сообщества (p/python, p/owasp-top-ten) и позволяет "
      "быстро писать собственные правила под архитектуру проекта."])

heading("3.3. SCA — анализ состава ПО и зависимостей", 2)
para("SCA (Software Composition Analysis) строит перечень сторонних компонентов приложения, "
     "включая транзитивные зависимости, и сопоставляет их версии с базами известных "
     "уязвимостей: CVE/NVD, GitHub Advisory Database (GHSA), Python Packaging Advisory "
     "Database (PYSEC) и агрегатором OSV. Для каждой уязвимости известна оценка CVSS "
     "и версия, в которой она исправлена. Это соответствует категории OWASP Top 10 "
     "A06:2021 «Vulnerable and Outdated Components». Особенность SCA — результат меняется "
     "без изменения кода: новая CVE в используемой библиотеке появляется в любой день, "
     "поэтому пайплайн запускается и по расписанию.")
rich([("b", "pip-audit"), " (PyPA) разрешает полное дерево зависимостей requirements.txt "
      "и проверяет его по базе PyPI/OSV. ", ("b", "Trivy"), " (Aqua Security) — универсальный "
      "сканер файловой системы, образов контейнеров и IaC с собственной базой уязвимостей."])

heading("3.4. Поиск секретов и формат SARIF", 2)
para("Утечка ключей и паролей в репозиторий — отдельный класс проблем: секрет остаётся в "
     "истории git даже после удаления из текущей версии. Gitleaks и GitLab Secret Detection "
     "проверяют всю историю коммитов по сигнатурам и энтропии строк.")
para("SARIF (Static Analysis Results Interchange Format, OASIS) — стандартный JSON-формат "
     "результатов статического анализа. GitHub принимает SARIF через действие "
     "upload-sarif и показывает находки во вкладке Security → Code scanning и прямо в diff "
     "pull request. GitLab использует собственные форматы отчётов "
     "(artifacts:reports:sast, dependency_scanning), которые отображаются в виджете "
     "Merge Request и в Security Dashboard.")
table(["Подход", "Что анализирует", "Когда", "Примеры находок", "Инструменты"],
      [["SAST", "исходный код (AST, потоки данных)", "commit / PR",
        "SQLi, OS command injection, слабый хеш, секрет в коде", "Bandit, Semgrep, CodeQL"],
       ["SCA", "зависимости и их версии", "commit / PR + расписание",
        "CVE в библиотеках, лицензии", "pip-audit, Trivy, Dependabot"],
       ["Secrets", "история git", "commit / PR", "API-ключи, пароли, токены",
        "Gitleaks, Secret Detection"],
       ["DAST", "работающее приложение", "после деплоя на стенд",
        "ошибки конфигурации, XSS, IDOR", "OWASP ZAP, Burp"]],
      [2.0, 3.6, 2.9, 4.4, 3.6], "Сравнение видов автоматического тестирования безопасности")

heading("3.5. Ролевая модель доступа RBAC", 2)
para("RBAC (Role-Based Access Control) — модель, в которой права (permissions) выдаются не "
     "пользователям напрямую, а ролям, а пользователь получает права через назначенные ему "
     "роли. Стандарт NIST RBAC (ANSI INCITS 359) выделяет четыре уровня модели.")
table(["Уровень NIST RBAC", "Содержание", "Реализация в работе"],
      [["Core (базовый)", "пользователи, роли, права, сеансы; связи многие-ко-многим",
        "таблицы users, roles, permissions, user_roles, role_permissions"],
       ["Hierarchical", "иерархия ролей: старшая роль наследует права младшей",
        "задана составом прав: ADMIN ⊃ MODERATOR ⊃ USER"],
       ["Constrained (SSD/DSD)", "разделение обязанностей: несовместимые роли",
        "не требуется заданием; set_role назначает одну роль"],
       ["Symmetric", "обзор прав: какие роли и пользователи имеют право X",
        "запрос GET /api/v1/admin/users и SQL-запрос прав пользователя"]],
      [3.6, 6.0, 6.9], "Уровни модели NIST RBAC")
para("Принцип наименьших привилегий (PoLP) требует давать каждой роли только права, "
     "необходимые для её задач, и запрещать всё, что явно не разрешено (deny by default). "
     "Проверка выполняется на сервере для каждого запроса: скрытие кнопок в интерфейсе "
     "защитой не является. Типичные ошибки — эндпоинт без проверки права (Broken Function "
     "Level Authorization, эскалация привилегий), доступ к чужому объекту по идентификатору "
     "(IDOR / BOLA) и возможность самому назначить себе роль через тело запроса "
     "(Mass Assignment).")

# --- 4. Среда --------------------------------------------------------------
heading("4. Среда выполнения и инструменты")
table(["Компонент", "Версия / значение"],
      [["ОС (локальный прогон)", "Windows 11 Pro"],
       ["Python (локально / в CI)", "3.10.7 / 3.12"],
       ["FastAPI · PyJWT · PyYAML (после исправления)",
        f"{version('fastapi')} · {version('pyjwt')} · {version('pyyaml')}"],
       ["pytest · requests (клиент API-тестов)", f"{version('pytest')} · {version('requests')}"],
       ["Postman", "коллекция и окружение в формате Postman Collection v2.1"],
       ["СУБД", "SQLite (демонстрационный стенд); SQL-скрипт для PostgreSQL"],
       ["Bandit", version("bandit")],
       ["Semgrep", version("semgrep")],
       ["pip-audit", version("pip-audit")],
       ["Trivy (в CI)", "aquasecurity/trivy-action v0.36.0, образ aquasec/trivy:0.67.2"],
       ["Gitleaks (в CI / локально)", "gitleaks/gitleaks-action@v3 / gitleaks 8.30.1"],
       ["Репозиторий GitHub", "github.com/is1am/cicd-security-pipeline"],
       ["Система контроля версий", "git, ветка main"]],
      [8.0, 8.5], "Среда выполнения и версии инструментов")

table(["Путь", "Назначение"],
      [["app/main.py, app/security.py, app/db.py", "RBAC-сервис на FastAPI (объект проверки)"],
       ["tests/test_rbac.py", "функциональные и негативные тесты RBAC (pytest)"],
       ["sql/rbac_schema.sql", "SQL-скрипт схемы RBAC для PostgreSQL с начальными данными"],
       ["postman/*.json", "Postman-коллекция (21 запрос) и окружение"],
       ["scripts/run_collection.py", "запуск сервиса и выполнение Postman-коллекции"],
       [".github/workflows/security.yml", "пайплайн GitHub Actions"],
       [".github/dependabot.yml", "автоматические PR с обновлением зависимостей"],
       [".gitlab-ci.yml", "пайплайн GitLab CI"],
       [".semgrep/rbac-rules.yml", "собственные правила Semgrep"],
       ["security-policy.json", "политика Security Gate (пороги и исключения)"],
       [".gitleaks.toml", "стандартные правила Gitleaks + исключение для reports/"],
       ["scripts/security_gate.py", "сводка отчётов и решение «пропустить / заблокировать»"],
       ["scripts/run_local_scans.py", "локальный прогон тех же проверок, что и в CI"],
       ["reports/before, reports/after", "отчёты сканеров до и после исправлений"]],
      [7.0, 9.5], "Структура проекта ПР5_CICD_Security")

# --- 5. Объект проверки ----------------------------------------------------
heading("5. Объект проверки: RBAC-сервис")
heading("5.1. Модель данных", 2)
para("Сервис реализует классическую модель RBAC из методических указаний: права "
     "(permissions) назначаются ролям, роли — пользователям. Связи многие-ко-многим "
     "реализованы таблицами user_roles и role_permissions с составными первичными ключами. "
     "Внешние ключи объявлены с ON DELETE CASCADE и ON UPDATE CASCADE: при удалении "
     "пользователя или роли связи удаляются автоматически, и «висячих» назначений прав "
     "не остаётся.")
figure("screenshots/er_rbac.png", "ER-диаграмма базы данных RBAC", 16.5)
code(src("sql/rbac_schema.sql", "CREATE TABLE users (", "CREATE INDEX idx_role_permissions_perm"))
para("Листинг 1 — SQL-скрипт создания таблиц (sql/rbac_schema.sql, PostgreSQL)", indent=False,
     size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
table(["Роль", "Права"],
      [["ADMIN", "READ_PUBLIC, VIEW_AUDIT, EXPORT_AUDIT, MANAGE_USERS"],
       ["MODERATOR", "READ_PUBLIC, VIEW_AUDIT"],
       ["USER", "READ_PUBLIC"]],
      [4.0, 12.5], "Матрица «роль — права»")

heading("5.2. Middleware проверки прав", 2)
para("Проверка реализована зависимостями FastAPI. get_current_user проверяет подпись и срок "
     "действия JWT и то, что учётная запись существует и активна (is_active). "
     "Фабрика require_permission(\"ПРАВО\") создаёт зависимость, которая при каждом "
     "запросе получает права пользователя из БД одним SQL-запросом через user_roles и "
     "role_permissions и возвращает 403 Forbidden, если нужного права нет. Проверяется "
     "право, а не имя роли: добавление новой роли не требует правки кода эндпоинтов.")
code(src("app/main.py", "def get_current_user", "    return dependency"))
para("Листинг 2 — проверка токена и разрешений (app/main.py)", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)
code(src("app/main.py", '@app.get("/api/v1/admin/users")', '    return {"id": user_id, "role": body.role}'))
para("Листинг 3 — административные эндпоинты, защищённые правом MANAGE_USERS", indent=False,
     size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Роль в теле запроса POST /api/v1/admin/users ограничена типом "
     "Literal[\"USER\", \"MODERATOR\", \"ADMIN\"]: неизвестное значение отклоняется с кодом "
     "422 до обращения к БД. Назначать роли может только обладатель MANAGE_USERS, поэтому "
     "модератор не может создать администратора (защита от Mass Assignment и эскалации).")

heading("5.3. Эндпоинты и намеренные уязвимости", 2)
table(["Эндпоинт", "Требуемое право", "Роли"],
      [["POST /api/v1/auth/login", "—", "все (выдача JWT)"],
       ["GET /api/v1/public", "READ_PUBLIC", "USER, MODERATOR, ADMIN"],
       ["GET /api/v1/users/search", "READ_PUBLIC", "USER, MODERATOR, ADMIN"],
       ["GET /api/v1/moderator/audit", "VIEW_AUDIT", "MODERATOR, ADMIN"],
       ["GET /api/v1/moderator/audit/export", "EXPORT_AUDIT", "ADMIN"],
       ["GET /api/v1/admin/users", "MANAGE_USERS", "ADMIN"],
       ["POST /api/v1/admin/users", "MANAGE_USERS", "ADMIN"],
       ["PUT /api/v1/admin/users/{id}/role", "MANAGE_USERS", "ADMIN"],
       ["POST /api/v1/admin/import", "MANAGE_USERS", "ADMIN"]],
      [7.0, 4.0, 5.5], "Эндпоинты сервиса и права доступа")
para("В исходную версию (коммит " + BASE[:7] + ") намеренно внесены ошибки, которые часто "
     "встречаются в реальных проектах:")
table(["№", "Ошибка", "Где", "CWE / OWASP"],
      [["1", "SQL-запрос собирается f-строкой из параметра q", "main.py, /users/search",
        "CWE-89 · A03 Injection"],
       ["2", "Вызов оболочки ОС с shell=True и параметром запроса", "main.py, /audit/export",
        "CWE-78 · A03 Injection"],
       ["3", "Эндпоинт экспорта не проверяет право EXPORT_AUDIT", "main.py, /audit/export",
        "CWE-285 · A01 Broken Access Control"],
       ["4", "yaml.load с yaml.Loader (создание произвольных объектов)", "main.py, /admin/import",
        "CWE-502 · A08"],
       ["5", "Секрет подписи JWT в исходном коде", "security.py", "CWE-798 · A07"],
       ["6", "JWT декодируется без проверки подписи", "security.py", "CWE-347 · A02"],
       ["7", "Пароли хешируются MD5 без соли", "security.py", "CWE-327/916 · A02"],
       ["8", "Сервер слушает 0.0.0.0", "main.py", "CWE-605 · A05"],
       ["9", "Устаревшие версии fastapi, PyJWT, requests, Jinja2", "requirements.txt",
        "A06 Vulnerable Components"]],
      [0.8, 7.2, 4.0, 4.5], "Уязвимости исходной версии")

# --- 6. Пайплайн -----------------------------------------------------------
heading("6. Реализация пайплайна безопасности")
heading("6.1. Архитектура", 2)
para("Пайплайн запускается при push и pull request в ветку main, еженедельно по расписанию "
     "(чтобы обнаруживать новые CVE в неизменном коде) и вручную. Проверки выполняются "
     "параллельно в отдельных джобах, каждая сохраняет машиночитаемый отчёт (JSON) "
     "и, где возможно, SARIF. Финальная джоба Security Gate собирает отчёты и по политике "
     "принимает решение. В настройках репозитория (branch protection) статус Security Gate "
     "делается обязательным, поэтому изменение с блокирующей находкой нельзя слить.")
figure("screenshots/pipeline.png", "Архитектура CI/CD Security Pipeline", 16.5)

heading("6.2. GitHub Actions", 2)
para("Файл .github/workflows/security.yml. Основные решения:")
bullets([
    [("code", "permissions: contents: read"), " на уровне workflow и ",
     ("code", "security-events: write"), " только в джобах, загружающих SARIF — принцип "
     "наименьших привилегий для GITHUB_TOKEN;"],
    "версии сканеров и Docker-образов зафиксированы (воспроизводимость, защита от "
    "подмены инструмента); для production рекомендуется закреплять actions по SHA коммита;",
    "Bandit, Semgrep и Trivy загружают SARIF в Code Scanning (category разделяет инструменты);",
    "Gitleaks получает полную историю (fetch-depth: 0);",
    "сканеры не прерывают джобу сами (--exit-zero / || true): решение принимает Security Gate "
    "по единой политике, а отчёты сохраняются как артефакты даже при наличии находок;",
    [("code", "concurrency"), " отменяет устаревшие запуски той же ветки."],
])
code(src(".github/workflows/security.yml", "  sast-semgrep:", "          category: semgrep"))
para("Листинг 4 — джоба Semgrep в GitHub Actions", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)
code(src(".github/workflows/security.yml", "  security-gate:", "run: python scripts"))
para("Листинг 5 — джоба Security Gate в GitHub Actions", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)

heading("6.3. GitLab CI", 2)
para("Файл .gitlab-ci.yml реализует ту же логику в стадиях test → security → gate. "
     "Встроенный шаблон Jobs/Secret-Detection подключается через include. Semgrep формирует "
     "отчёт в формате GitLab SAST (--gitlab-sast-output), Trivy — отчёт dependency_scanning "
     "по шаблону gitlab.tpl; оба публикуются через artifacts:reports и отображаются в "
     "Merge Request. Собственные джобы не требуют тарифа Ultimate.")
code(src(".gitlab-ci.yml", "sast:semgrep:", "      sast: gl-sast-report.json"))
para("Листинг 6 — джоба Semgrep в GitLab CI", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)
code(src(".gitlab-ci.yml", "sca:trivy:", "      dependency_scanning:"))
para("Листинг 7 — джоба Trivy в GitLab CI", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)

heading("6.4. Собственные правила Semgrep для RBAC", 2)
para("Стандартные правила не знают, что в проекте права проверяются через "
     "require_permission. Поэтому написано правило rbac-privileged-route-without-permission: "
     "оно срабатывает на любой маршрут /api/v1/admin/* или /api/v1/moderator/*, у которого "
     "нет зависимости Depends(require_permission(...)) ни в параметрах функции, ни в "
     "dependencies декоратора. Так SAST начинает находить ошибку контроля доступа "
     "(OWASP API5 Broken Function Level Authorization), которую обычные сканеры пропускают. "
     "Ещё два правила запрещают декодирование JWT без проверки подписи и секрет в коде.")
code("\n".join(src(".semgrep/rbac-rules.yml",
                    "  - id: rbac-privileged-route-without-permission",
                    "  - id: jwt-decode-without-verification").splitlines()[:-2]))
para("Листинг 8 — правило Semgrep для проверки RBAC-маршрутов", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)

heading("6.5. Security Gate и политика", 2)
para("Скрипт scripts/security_gate.py читает bandit.json, semgrep.json, pip-audit.json "
     "и trivy.json, нормализует находки, устраняет дубли (pip-audit выдаёт одну уязвимость "
     "под несколькими идентификаторами — GHSA, PYSEC, CVE) и применяет политику "
     "security-policy.json. Сборка блокируется, если есть хотя бы одна блокирующая находка "
     "или отсутствует отчёт одного из сканеров (сломанный сканер не должен означать "
     "«уязвимостей нет»). Сводка в Markdown публикуется в GITHUB_STEP_SUMMARY.")
code((ROOT / "security-policy.json").read_text(encoding="utf-8"))
para("Листинг 9 — политика security-policy.json", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)
para("Исключение допускается только адресно (идентификатор правила + файл), "
     "с обоснованием и сроком действия: по истечении срока находка снова блокирует сборку. "
     "Это защищает от бесконтрольного накопления «временных» подавлений.")

# --- 7. Результаты до исправлений ------------------------------------------
heading("7. Результаты сканирования исходной версии")
para("Все проверки выполнены командой python scripts/run_local_scans.py before — она "
     "запускает те же инструменты с теми же параметрами, что и джобы пайплайна, и "
     "сохраняет отчёты в reports/before.")
heading("7.1. Тесты", 2)
para("Из пяти тестов три упали: пользователь с ролью USER получил доступ к экспорту аудита "
     "(200 вместо 403), токен, подписанный ключом злоумышленника, принят (200 вместо 401), "
     "а запрос с параметром zzz' OR 1=1 -- вернул всех пользователей.")
figure("screenshots/pytest_before.png", "pytest на исходной версии: 3 из 5 тестов не пройдены", 15)

heading("7.2. SAST: Bandit", 2)
figure("screenshots/bandit_before.png", "Bandit: находки в исходной версии", 16)
para(f"Bandit нашёл {count(before, 'Bandit')} проблем, из них {count(before, 'Bandit', True)} "
     "блокирующих по политике (уровень и достоверность не ниже MEDIUM): SQL-инъекция (B608), "
     "shell=True (B602), yaml.load (B506), привязка к 0.0.0.0 (B104), MD5 (B324). "
     "Находки уровня LOW (импорт subprocess, строка «bearer») не блокируют сборку; "
     "«bearer» — ложное срабатывание, внесённое в исключения политики. Bandit отметил "
     "секрет в коде только как LOW и не обнаружил ни отключённую проверку подписи JWT, "
     "ни отсутствие проверки права на эндпоинте экспорта.")

heading("7.3. SAST: Semgrep", 2)
figure("screenshots/semgrep_before.png", "Semgrep: находки в исходной версии", 16)
para(f"Semgrep нашёл {count(before, 'Semgrep')} проблем — все блокирующие. Собственные правила "
     "обнаружили маршрут /api/v1/moderator/audit/export без require_permission (строка 79), "
     "декодирование JWT без проверки подписи и секрет в коде. Правила сообщества дополнительно "
     "указали на shell=True, yaml.load и MD5 для паролей. Bandit и Semgrep частично "
     "пересекаются, но каждый нашёл то, что пропустил другой, — поэтому в пайплайне оба.")

heading("7.4. SCA: pip-audit", 2)
figure("screenshots/pip_audit_before.png", "pip-audit: уязвимые зависимости исходной версии", 15)
sca = {}
for f in before["findings"]:
    if f["tool"] == "pip-audit":
        pkg, fix = f["where"].split(" → ")
        sca.setdefault(pkg, []).append((f["id"], fix))
rows = []
for pkg, items in sca.items():
    fixes = [x[1] for x in items if x[1] != "нет"]
    direct = pkg.split()[0] in old_req.lower()
    rows.append([pkg, "прямая" if direct else "транзитивная (через fastapi)",
                 str(len(items)), ", ".join(x[0] for x in items[:3]) + (" …" if len(items) > 3 else ""),
                 max(fixes, key=lambda v: tuple(int(p) for p in re.findall(r"\d+", v))) if fixes else "—"])
table(["Пакет", "Зависимость", "Уязв.", "Примеры идентификаторов", "Исправлено в"],
      rows, [3.2, 3.6, 1.4, 5.6, 2.7], "Уязвимости зависимостей исходной версии (после удаления дублей)")
para(f"pip-audit вывел 49 записей, после удаления дублей — {count(before, 'pip-audit')} "
     f"уникальных уязвимостей в 5 пакетах; {count(before, 'pip-audit', True)} из них имеют "
     "исправленную версию и блокируют сборку. Важно, что starlette в requirements.txt не "
     "указан: это транзитивная зависимость fastapi, и её уязвимости (в т.ч. CVE-2024-47874 — "
     "отказ в обслуживании при разборе multipart) видны только при анализе полного дерева.")

heading("7.5. Решение Security Gate", 2)
figure("screenshots/gate_before.png", "Security Gate для исходной версии: сборка заблокирована", 12)
para(f"Итого блокирующих находок: {sum(f['blocking'] for f in before['findings'])}. "
     "Gate завершился с кодом 1, что в CI означает красный статус и запрет слияния.")

# --- 8. Исправление --------------------------------------------------------
heading("8. Устранение уязвимостей")
para("Исправления внесены отдельным коммитом " + FIX[:7] + ". Соответствие находок и "
     "исправлений приведено в таблице.")
table(["Находка", "Инструмент", "Исправление"],
      [["SQL-инъекция (B608)", "Bandit, тест", "параметризованный запрос с плейсхолдером ?"],
       ["shell=True (B602)", "Bandit, Semgrep", "CSV формируется модулем csv, оболочка не вызывается"],
       ["Маршрут без проверки права", "Semgrep (RBAC-правило), тест",
        "Depends(require_permission(\"EXPORT_AUDIT\"))"],
       ["yaml.load (B506)", "Bandit, Semgrep", "yaml.safe_load"],
       ["Секрет в коде", "Semgrep", "JWT_SECRET из окружения, проверка длины ≥ 32"],
       ["JWT без проверки подписи", "Semgrep, тест", "jwt.decode(key, algorithms=[\"HS256\"], "
        "require=[sub, exp])"],
       ["MD5 для паролей (B324)", "Bandit, Semgrep", "PBKDF2-HMAC-SHA256, соль 16 байт, "
        "600 000 итераций, compare_digest"],
       ["Привязка к 0.0.0.0 (B104)", "Bandit", "HOST из окружения, по умолчанию 127.0.0.1"],
       ["Уязвимые зависимости", "pip-audit", "обновление до актуальных версий, Dependabot"]],
      [4.6, 3.8, 8.1], "Исправления по результатам сканирования")
code("# Было\n" + snippet(old_sec, "def decode_token", "return jwt.decode") + "\n\n# Стало\n"
     + src("app/security.py", "def decode_token", 'options={"require"'))
para("Листинг 10 — проверка JWT до и после исправления", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)
code("# Было\n" + snippet(old_main, "        # SQL-инъекция", "fetchall()") + "\n\n# Стало\n"
     + src("app/main.py", "        # параметризованный", "fetchall()"))
para("Листинг 11 — поиск пользователей до и после исправления", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)
code("# Было\n" + snippet(old_main, '@app.get("/api/v1/moderator/audit/export")',
                          'return {"result"') + "\n\n# Стало\n"
     + src("app/main.py", '@app.get("/api/v1/moderator/audit/export")', 'return {"result"'))
para("Листинг 12 — эндпоинт экспорта аудита до и после исправления", indent=False, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER)
new_req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
pins = lambda t: dict(ln.split("==") for ln in t.split() if "==" in ln)
o, n = pins(old_req), pins(new_req)
table(["Пакет", "Было", "Стало"], [[k, o[k], n.get(k, "—")] for k in o],
      [6.0, 5.0, 5.5], "Изменение версий в requirements.txt")

# --- 9. После исправлений --------------------------------------------------
heading("9. Повторное сканирование")
para("Команда python scripts/run_local_scans.py after выполнена на исправленной версии, "
     "отчёты сохранены в reports/after.")
figure("screenshots/pytest_after.png", "pytest после исправлений: 8 из 8 тестов пройдены", 15)
figure("screenshots/scans_after.png", "Bandit и pip-audit после исправлений", 15)
figure("screenshots/gate_after.png", "Security Gate после исправлений: проверка пройдена", 12)
para("Bandit сообщает только о строке «bearer» уровня LOW — это тип токена OAuth 2.0, "
     "ложное срабатывание, внесённое в исключения политики с обоснованием и сроком. "
     "Semgrep и pip-audit находок не выдали.")
table(["Показатель", "До", "После"],
      [["Тесты pytest (пройдено)", "2 из 5", "8 из 8 (+3 теста RBAC)"],
       ["Bandit: всего / блокирующих", f"{count(before, 'Bandit')} / {count(before, 'Bandit', True)}",
        f"{count(after, 'Bandit')} / {count(after, 'Bandit', True)}"],
       ["Semgrep: всего / блокирующих",
        f"{count(before, 'Semgrep')} / {count(before, 'Semgrep', True)}",
        f"{count(after, 'Semgrep')} / {count(after, 'Semgrep', True)}"],
       ["pip-audit: уникальных CVE / блокирующих",
        f"{count(before, 'pip-audit')} / {count(before, 'pip-audit', True)}",
        f"{count(after, 'pip-audit')} / {count(after, 'pip-audit', True)}"],
       ["Решение Security Gate", "ЗАБЛОКИРОВАНО (exit 1)", "ПРОЙДЕН (exit 0)"]],
      [7.5, 4.5, 4.5], "Сравнение результатов до и после исправлений")

heading("9.1. Запуск в GitHub Actions", 2)
para("Проект опубликован в публичном репозитории github.com/is1am/cicd-security-pipeline. "
     "Первый запуск пайплайна (run #1) завершился с ошибкой, и разбор его результатов "
     "оказался полезным сам по себе.")
figure("screenshots/gh_run_fail.png", "Первый запуск в GitHub Actions (run #1): Trivy и Gitleaks не пройдены", 16)
table(["Джоба", "Результат", "Причина и исправление"],
      [["SCA · Trivy", "ошибка", "версия action указана как 0.33.1 вместо тега v0.33.1 — GitHub "
        "не нашёл action; исправлено на aquasecurity/trivy-action@v0.36.0"],
       ["Secrets · Gitleaks", "6 находок", "приватный EC-ключ, JWT и generic-api-key в "
        "reports/before/pip-audit.json — это примеры из текстов advisory PyJWT, попавшие в "
        "закоммиченный отчёт сканера (ложное срабатывание); добавлен .gitleaks.toml с "
        "исключением для каталога reports/"],
       ["Security Gate", "пройден (ошибка Gate)", "отчёт trivy.json отсутствовал, но Gate "
        "считал его необязательным; добавлен флаг --require-trivy, в CI отсутствие отчёта "
        "Trivy теперь блокирует сборку"],
       ["Все джобы", "предупреждения", "actions на Node 20 устарели; обновлены до "
        "checkout@v7, setup-python@v7, upload-artifact@v7, download-artifact@v8, "
        "gitleaks-action@v3"]],
      [3.4, 2.8, 10.3], "Разбор первого запуска в GitHub Actions")
para("Отдельно стоит отметить результат Gitleaks: строку rbac-super-secret-key-2026, "
     "которая действительно была секретом в исходной версии, он не обнаружил — её энтропия "
     "слишком низка для его эвристик. Этот секрет нашли только Semgrep (собственное правило "
     "hardcoded-jwt-secret и правило сообщества) и, с низким уровнем, Bandit. "
     "Это ещё один довод в пользу сочетания разных классов сканеров. Найденный в истории git "
     "секрет в реальном проекте нужно считать скомпрометированным и заменить, а не только "
     "удалить из текущей версии кода.")
para("Второй запуск (run #8, после исправлений) прошёл полностью: все семь джоб "
     "завершились успешно, Security Gate разрешил сборку. Dependabot, включённый файлом "
     ".github/dependabot.yml, сразу после публикации открыл pull request "
     "«Bump fastapi from 0.141.1 to 0.162.0» — SCA работает и вне пайплайна.")
figure("screenshots/gh_run_ok.png", "Запуск в GitHub Actions после исправлений (run #8): все проверки пройдены", 16)
para("Следующий запуск (run #10, коммит с Postman-коллекцией и результатами API-тестов) "
     "снова остановил Gitleaks: 5 находок типа jwt — поддельный токен из негативного теста "
     "и токены тестового стенда в reports/api/results.json. Локальная проверка Gitleaks "
     "8.30.1 находок не давала. Причина — gitleaks-action по умолчанию устанавливает более "
     "старую версию Gitleaks, которая не поддерживает синтаксис [[allowlists]] и молча "
     "игнорировала исключения. Исправление: конфигурация переписана в совместимом "
     "формате [allowlist], а версия зафиксирована переменной GITLEAKS_VERSION: 8.30.1. "
     "Вывод: версии сканеров в CI и на рабочем месте разработчика должны совпадать, иначе "
     "одна и та же политика даёт разные результаты.")

heading("10. Тестирование ролевой модели в Postman (Negative Testing)")
para("Тесты из шага 3 методических указаний оформлены как Postman-коллекция "
     "postman/RBAC_PR5.postman_collection.json и окружение RBAC_PR5.postman_environment.json "
     "(переменная baseUrl). Каждый запрос содержит тест pm.test(...) с ожидаемым "
     "статусом, а токены и идентификатор нового пользователя сохраняются в переменные "
     "окружения. Для воспроизводимого прогона используется скрипт "
     "scripts/run_collection.py: он запускает сервис на чистой БД, выполняет все запросы "
     "коллекции по порядку и проверяет статусы (аналог Newman). Ниже — результаты этого "
     "прогона; те же запросы выполняются вручную в Postman импортом двух JSON-файлов.")
figure("screenshots/api_run.png",
       f"Прогон Postman-коллекции: {api['summary']['passed']} из {api['summary']['total']} проверок пройдено", 15)
table(["Группа", "Запрос", "Ожидалось", "Получено"],
      [[r["folder"].split(". ", 1)[1], r["name"], str(r["expected"]), str(r["status"])]
       for r in api["results"]],
      [3.8, 7.7, 2.4, 2.6], "Результаты запросов Postman-коллекции")

heading("10.1. Тест 1 (позитивный)", 2)
para("Администратор входит в систему и создаёт пользователя. Сервер возвращает "
     "201 Created и идентификатор новой записи.")
figure("screenshots/api_t1.png", "Тест 1: вход ADMIN и создание пользователя — 201 Created", 15)

heading("10.2. Тест 2 (негативный)", 2)
para("Рядовой сотрудник (USER) с валидным токеном обращается к /api/v1/admin/users. "
     "Аутентификация проходит, но у роли USER нет права MANAGE_USERS, и middleware "
     "возвращает 403 Forbidden и для чтения списка, и для попытки создать администратора.")
figure("screenshots/api_t2.png", "Тест 2: USER → /api/v1/admin/users — 403 Forbidden", 15)
para("Дополнительно проверены попытки эскалации привилегий: модератор пытается создать "
     "пользователя с ролью ADMIN и выгрузить аудит (право EXPORT_AUDIT есть только у "
     "ADMIN) — 403; запрос без токена и с токеном, подписанным чужим ключом, — 401; "
     "создание пользователя с несуществующей ролью SUPERUSER — 422.")
figure("screenshots/api_neg.png", "Дополнительные негативные тесты: 403, 401, 422", 15)

heading("10.3. Тест 3: смена роли «на лету»", 2)
para("Новый сотрудник получает токен с ролью USER и получает 403 на /api/v1/moderator/audit. "
     "Затем администратор меняет ему роль на MODERATOR (PUT /api/v1/admin/users/{id}/role, "
     "т.е. UPDATE таблицы user_roles), и сотрудник повторяет запрос с тем же токеном.")
figure("screenshots/api_t3.png", "Тест 3: изменение роли без перевыпуска токена", 15)
para(f"Новая роль применилась на первом же запросе после изменения — через "
     f"{api['summary']['role_change_delay_ms']} мс, что равно времени одного HTTP-запроса; "
     "возврат роли USER так же сразу вернул 403. Задержки нет, потому что токен содержит "
     "только идентификатор пользователя (sub), а права читаются из БД при каждом "
     "запросе. Для сравнения ниже приведён альтернативный вариант, когда роль хранится "
     "в claims JWT.")
table(["Критерий", "Права из БД при каждом запросе (реализовано)", "Роль в claims JWT"],
      [["Задержка применения новой роли", "0 — следующий запрос",
        "до истечения exp (15 мин) или до перевыпуска токена"],
       ["Отзыв прав / блокировка", "сразу (роль или is_active в БД)",
        "токен действует до exp; нужен blacklist по jti"],
       ["Нагрузка", "1 SQL-запрос на каждый запрос API (кэш с коротким TTL)",
        "проверка без обращения к БД"],
       ["Риск", "нагрузка на БД", "окно, в котором уволенный или пониженный "
        "сотрудник сохраняет права"]],
      [4.3, 6.0, 6.2], "Где хранить роли: сравнение подходов")
para("Для корпоративных систем, где своевременный отзыв прав важнее нескольких "
     "миллисекунд на запрос, выбран вариант с чтением прав из БД. Если роль всё же "
     "передаётся в токене, срок жизни access-токена должен быть коротким, а при смене "
     "роли — инвалидироваться refresh-токен и вестись список отозванных jti.")

# --- 10. GitHub vs GitLab --------------------------------------------------
heading("11. Сравнение GitHub Actions и GitLab CI")
table(["Критерий", "GitHub Actions", "GitLab CI"],
      [["Описание пайплайна", ".github/workflows/*.yml, jobs + needs",
        ".gitlab-ci.yml, stages + needs"],
       ["Готовые компоненты", "Marketplace: trivy-action, gitleaks-action, upload-sarif",
        "шаблоны include: SAST, Secret-Detection, Dependency-Scanning"],
       ["Показ находок", "SARIF → Security / Code scanning, аннотации в PR",
        "artifacts:reports → виджет MR, Security Dashboard"],
       ["Ограничения тарифа", "Code scanning бесплатен для публичных репозиториев",
        "Dependency Scanning и Security Dashboard — Ultimate; собственные джобы — на любом"],
       ["Права токена", "permissions на уровне workflow и job", "CI_JOB_TOKEN, protected-переменные"],
       ["Обновление зависимостей", "Dependabot", "Renovate / Dependency Scanning"],
       ["Блокировка слияния", "branch protection: required status checks",
        "«Pipelines must succeed», approval policies"]],
      [3.8, 6.3, 6.4], "Реализация пайплайна в двух CI-системах")
para("Пайплайн GitHub Actions проверен реальными запусками в репозитории "
     "github.com/is1am/cicd-security-pipeline. Конфигурация GitLab CI реализует ту же "
     "логику на тех же инструментах и командах, но в GitLab в рамках работы не запускалась.")

# --- 11. Выводы ------------------------------------------------------------
heading("12. Выводы")
para("1. Построен конвейер безопасности для GitHub Actions и GitLab CI, который при каждом "
     "изменении и еженедельно по расписанию выполняет SAST (Bandit, Semgrep), SCA "
     "(pip-audit, Trivy), поиск секретов (Gitleaks / Secret Detection) и тесты. "
     "Решение о допуске изменения принимает единый Security Gate по явной политике.")
para(f"2. На исходной версии RBAC-сервиса пайплайн обнаружил "
     f"{sum(f['blocking'] for f in before['findings'])} блокирующих находок: инъекции SQL и "
     "команд ОС, небезопасную десериализацию, секрет в коде, отключённую проверку подписи "
     f"JWT, MD5 для паролей и {count(before, 'pip-audit')} известных уязвимостей в 5 пакетах, "
     "включая транзитивную зависимость starlette. После исправлений все проверки пройдены.")
para("3. Ни один инструмент не нашёл всё в одиночку: Bandit не заметил отключённую проверку "
     "подписи JWT и отсутствие проверки права; правила сообщества Semgrep не знают о "
     "require_permission. Комбинация нескольких сканеров и собственных правил, учитывающих "
     "архитектуру проекта, существенно повышает полноту анализа.")
para("4. Ролевая модель спроектирована по NIST RBAC (Core и иерархия через состав прав): "
     "права назначаются ролям, роли — пользователям, проверка выполняется на сервере по "
     "праву, а не по имени роли, и по умолчанию запрещено всё, что не разрешено явно. "
     f"Postman-тесты ({api['summary']['passed']} из {api['summary']['total']} пройдено) "
     "подтвердили: USER получает 403 на административных ресурсах, модератор не может "
     "создать администратора и выгрузить аудит, поддельный токен отклоняется с 401, "
     "а неизвестная роль — с 422.")
para("5. Правильно спроектированный RBAC предотвращает эскалацию привилегий, потому что "
     "у пользователя нет пути получить право, не выданное его роли: назначать роли может "
     "только обладатель MANAGE_USERS, роль в запросе ограничена белым списком, а права "
     "читаются из БД при каждом запросе. Поэтому понижение роли или блокировка учётной "
     "записи действуют сразу (тест 3 — без задержки), и у скомпрометированной или "
     "уволенной учётной записи не остаётся окна, в котором старые права ещё работают.")
para("6. Для RBAC-систем особенно важно собственное правило SAST, проверяющее, что каждый "
     "привилегированный маршрут защищён проверкой права. Оно превращает ошибку контроля "
     "доступа (эскалацию привилегий) из находки пентеста в автоматическую проверку каждого "
     "pull request. Негативные тесты (403 для USER, 401 для поддельного токена) дополняют "
     "SAST, подтверждая поведение на работающем приложении.")
para("7. SCA должен анализировать полное дерево зависимостей и запускаться по расписанию: "
     "уязвимости появляются в библиотеках без изменения кода проекта. Автоматические PR "
     "Dependabot сокращают время от публикации CVE до обновления.")
para("8. Эффективность пайплайна определяют не только сканеры, но и процесс: обязательный "
     "статус в branch protection, минимальные права токена CI, зафиксированные версии "
     "инструментов, блокировка при отсутствии отчёта и исключения только с обоснованием "
     "и сроком действия.")

doc.save(OUT)
print("saved", OUT.name)
