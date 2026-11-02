# security_gate.py
# Security Gate: собирает отчёты Bandit, Semgrep, pip-audit, Trivy,
# применяет политику (security-policy.json) и завершает работу с кодом 1,
# если есть блокирующие находки. Отсутствующий отчёт тоже блокирует сборку.
# Запуск: python scripts/security_gate.py reports --policy security-policy.json [--summary out.md]

import argparse
import datetime
import json
import pathlib
import sys

LEVELS = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def norm(path):
    return str(path).replace("\\", "/").lstrip("./")


def load(folder, name):
    p = folder / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def ignored(policy, rule_id, path=""):
    today = datetime.date.today().isoformat()
    for rule in policy.get("ignore", []):
        if rule["id"] == rule_id and rule.get("expires", "9999") >= today \
                and (not rule.get("path") or norm(rule["path"]) == norm(path)):
            return True
    return False


def collect(folder, policy):
    """Возвращает список находок: (инструмент, тип, id, где, уровень, блокирует)."""
    block = policy["block"]
    findings, missing = [], []

    bandit = load(folder, "bandit.json")
    if bandit is None:
        missing.append("bandit.json")
    else:
        for r in bandit["results"]:
            sev, conf = r["issue_severity"], r["issue_confidence"]
            blocking = (LEVELS[sev] >= LEVELS[block["bandit_min_severity"]]
                        and LEVELS[conf] >= LEVELS[block["bandit_min_confidence"]]
                        and not ignored(policy, r["test_id"], r["filename"]))
            findings.append(("Bandit", "SAST", f"{r['test_id']} {r['test_name']}",
                             f"{norm(r['filename'])}:{r['line_number']}", sev, blocking))

    semgrep = load(folder, "semgrep.json")
    if semgrep is None:
        missing.append("semgrep.json")
    else:
        for r in semgrep["results"]:
            sev = r["extra"]["severity"]
            rule = r["check_id"].split(".")[-1]
            blocking = sev in block["semgrep_severities"] and not ignored(policy, rule, r["path"])
            findings.append(("Semgrep", "SAST", rule, f"{norm(r['path'])}:{r['start']['line']}",
                             sev, blocking))

    audit = load(folder, "pip-audit.json")
    if audit is None:
        missing.append("pip-audit.json")
    else:
        seen = set()     # pip-audit может повторять одну уязвимость под разными id
        for dep in audit["dependencies"]:
            for v in dep.get("vulns", []):
                vid = next((a for a in v.get("aliases", []) if a.startswith("CVE-")), v["id"])
                if (dep["name"], vid) in seen:
                    continue
                seen.add((dep["name"], vid))
                fix = ", ".join(v.get("fix_versions", [])) or "нет"
                blocking = (bool(v.get("fix_versions")) or not block["sca_block_if_fix_available"]) \
                    and not ignored(policy, vid)
                findings.append(("pip-audit", "SCA", vid,
                                 f"{dep['name']} {dep['version']} → {fix}", "—", blocking))

    trivy = load(folder, "trivy.json")
    if trivy is not None:      # Trivy есть только в CI; локально отчёт необязателен
        for res in trivy.get("Results", []):
            for v in res.get("Vulnerabilities") or []:
                blocking = v["Severity"] in block["trivy_severities"] \
                    and not ignored(policy, v["VulnerabilityID"])
                findings.append(("Trivy", "SCA", v["VulnerabilityID"],
                                 f"{v['PkgName']} {v['InstalledVersion']} → "
                                 f"{v.get('FixedVersion') or 'нет'}", v["Severity"], blocking))
    return findings, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=pathlib.Path)
    ap.add_argument("--policy", type=pathlib.Path, default=pathlib.Path("security-policy.json"))
    ap.add_argument("--summary", help="куда записать Markdown-сводку (например, $GITHUB_STEP_SUMMARY)")
    ap.add_argument("--json", help="куда записать результат в JSON")
    args = ap.parse_args()

    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    findings, missing = collect(args.folder, policy)
    blocking = [f for f in findings if f[5]]

    lines = ["## Security Gate", "",
             "| Инструмент | Тип | Всего | Блокирующих |", "|---|---|---|---|"]
    for tool, kind in [("Bandit", "SAST"), ("Semgrep", "SAST"), ("pip-audit", "SCA"), ("Trivy", "SCA")]:
        sub = [f for f in findings if f[0] == tool]
        lines.append(f"| {tool} | {kind} | {len(sub)} | {sum(f[5] for f in sub)} |")
    if missing:
        lines += ["", f"Отсутствуют отчёты: {', '.join(missing)}"]
    if blocking:
        lines += ["", "### Блокирующие находки", "", "| Инструмент | Правило / CVE | Где | Уровень |",
                  "|---|---|---|---|"]
        lines += [f"| {t} | {i} | {w} | {s} |" for t, _, i, w, s, _ in blocking]
    ok = not blocking and not missing
    lines += ["", "**Результат: ПРОЙДЕН ✅**" if ok else "**Результат: ЗАБЛОКИРОВАНО ❌**"]

    text = "\n".join(lines) + "\n"
    sys.stdout.buffer.write(text.encode("utf-8"))
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"passed": ok, "missing": missing,
             "findings": [dict(zip(["tool", "type", "id", "where", "severity", "blocking"], f))
                          for f in findings]}, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
