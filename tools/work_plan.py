"""План работ: проверка, отчёт, следующий пакет и генерация текста задачи (docs/work_plan.json).

python tools/work_plan.py [--plan файл.json] check
python tools/work_plan.py [--plan файл.json] render
python tools/work_plan.py next
python tools/work_plan.py prompt A1
python tools/work_plan.py set A1 wip|done|planned
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path(os.environ["WORK_PLAN_FILE"]) if os.environ.get("WORK_PLAN_FILE") else ROOT / "docs" / "work_plan.json"
OUT = PLAN.with_name("WORK_PLAN.md")
STATUSES = ("planned", "wip", "done")
SHARED_OK = ("docs/qa/",)

def load():
    return json.loads(PLAN.read_text(encoding="utf-8"))

def save(plan):
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

def prefix(glob):
    for i, ch in enumerate(glob):
        if ch in "*?[":
            return glob[:i]
    return glob

def overlap(a, b):
    if a.startswith(SHARED_OK) and b.startswith(SHARED_OK):
        return False
    pa, pb = prefix(a), prefix(b)
    return pa.startswith(pb) or pb.startswith(pa)

def zones(plan, pkg):
    return plan["lanes"][pkg["lane"]]["zone"] + pkg.get("zone_extra", [])

def validate(plan):
    errors = []
    pkgs = {p["id"]: p for p in plan["packages"]}
    if len(pkgs) != len(plan["packages"]):
        errors.append("повторяющиеся id")
    for p in plan["packages"]:
        if p["status"] not in STATUSES:
            errors.append(f'{p["id"]}: статус {p["status"]}')
        if p["lane"] not in plan["lanes"]:
            errors.append(f'{p["id"]}: неизвестная линия')
        for d in p["depends_on"]:
            if d not in pkgs:
                errors.append(f'{p["id"]}: нет зависимости {d}')
            elif pkgs[d]["step"] > p["step"] or (pkgs[d]["step"] == p["step"] and d != p["id"] and pkgs[d]["lane"] == p["lane"]):
                errors.append(f'{p["id"]}: зависимость {d} не раньше по шагу')
        if not p["done_when"] or not p["goal"]:
            errors.append(f'{p["id"]}: нет цели или критериев')
    steps = {}
    for p in plan["packages"]:
        steps.setdefault(p["step"], {}).setdefault(p["lane"], []).append(p)
    for s, lanes in steps.items():
        for lane, items in lanes.items():
            if len(items) > 1:
                errors.append(f"шаг {s}: больше одного пакета на линию {lane}")
        if "A" in lanes and "B" in lanes:
            for a in lanes["A"]:
                for b in lanes["B"]:
                    if b["id"] in a["depends_on"] or a["id"] in b["depends_on"]:
                        errors.append(f'шаг {s}: {a["id"]} и {b["id"]} зависят друг от друга, параллельность нарушена')
                    for za in zones(plan, a):
                        for zb in zones(plan, b):
                            if overlap(za, zb):
                                errors.append(f'шаг {s}: зоны пересекаются {za} и {zb}')
    shared = plan["rules"]["shared_files_director_only"]
    for p in plan["packages"]:
        for z in zones(plan, p):
            if any(overlap(z, s) for s in shared):
                errors.append(f'{p["id"]}: зона {z} пересекается с общими файлами директора')
    seen, stack = set(), set()
    def dfs(i):
        if i in stack:
            errors.append(f"цикл через {i}")
            return
        if i in seen:
            return
        seen.add(i); stack.add(i)
        for d in pkgs[i]["depends_on"]:
            if d in pkgs:
                dfs(d)
        stack.discard(i)
    for i in pkgs:
        dfs(i)
    return errors

def ready(plan):
    done = {p["id"] for p in plan["packages"] if p["status"] == "done"}
    return [p for p in plan["packages"] if p["status"] == "planned" and all(d in done for d in p["depends_on"])]

def render(plan):
    mark = {"planned": "ожидает", "wip": "в работе", "done": "готово"}
    rd = {p["id"] for p in ready(plan)}
    lines = ["# План работ: этапы и две независимые линии исполнителей", "",
             "Источник правды: [`work_plan.json`](work_plan.json). Файл собирается командой `python tools/work_plan.py render`, вручную не правится. Проверка `python tools/work_plan.py check`.", "",
             "Две линии работают одновременно и не пересекаются по файлам: **A (Сервер)** и **B (Клиент)**. Линия B строит экраны по контрактам из GDD на моках (mock-first), поэтому не ждёт сервер. Директор проектирует, проверяет и сливает в `main`; исполнители работают в своих ветках `v1/<id>-<slug>` и не меняют общие файлы.", ""]
    for key, lane in plan["lanes"].items():
        lines += [f"## Линия {key}: {lane['name']} ({lane['who']})", lane["note"], "", "Зона файлов: " + ", ".join(f"`{z}`" for z in lane["zone"]), ""]
    lines += ["## Шаги", "", "| Шаг | Линия A: сервер | Линия B: клиент |", "|---|---|---|"]
    steps = sorted({p["step"] for p in plan["packages"]})
    by = {(p["step"], p["lane"]): p for p in plan["packages"]}
    def cell(p):
        if not p:
            return "—"
        tag = "▶ можно выдавать" if p["id"] in rd else mark[p["status"]]
        return f'**{p["id"]}** {p["title"]} (GDD {", ".join(p["gdd"])}) · {tag}'
    for s in steps:
        lines.append(f'| {s} | {cell(by.get((s, "A")))} | {cell(by.get((s, "B")))} |')
    lines += ["", "## Правила", "",
              "1. Выдавать только пакеты со статусом «можно выдавать» (все зависимости готовы): `python tools/work_plan.py next`.",
              "2. Текст задания генерируется: `python tools/work_plan.py prompt A1`.",
              "3. Исполнитель не меняет общие файлы директора: " + ", ".join(f"`{x}`" for x in plan["rules"]["shared_files_director_only"]) + ".",
              "4. Новые флаги серверных механик выключены по умолчанию; включает только владелец.",
              "5. Слияние в `main` делает директор после пробного слияния, полного набора серверных тестов на PostgreSQL и всех клиентских проверок.", "",
              "## Доска задач (страница для владельца)", "",
              "Интерактивная страница с этапами по порядку, готовыми промптами, самопроверкой исполнителя, приёмкой директора и архивом. Собирается из этого плана: `python tools/work_board/build.py board.html`, публикуется как Artifact с общей базой (`db`, запись только владельцу). Состояние хранится в коллекции `tasks`, документ на пакет: `status` (`planned`, `issued`, `submitted`, `accepted`), `issuedAt`, `submittedAt`, `acceptedAt`, `merged`, `sha`, `note`. После изменения плана доску пересобирают и публикуют на тот же адрес, состояние сохраняется.", ""]
    return "\n".join(lines)

def prompt(plan, pid):
    p = next(x for x in plan["packages"] if x["id"] == pid)
    lane = plan["lanes"][p["lane"]]
    zone = zones(plan, p)
    gdds = ", ".join(f"docs/gdd/{g}_*.md" for g in p["gdd"])
    report = (lane.get("report") or "docs/qa/{id}.md").format(id=pid)
    proj = plan.get("project", {})
    repo = proj.get("repo") or "репозиторий проекта"
    branch = proj.get("branch") or "main"
    pattern = plan["rules"].get("branch_pattern", "<id>-<кратко>").replace("<id>", pid.lower()).replace("<slug>", "<кратко>")
    rules = [
        "Один большой заход, вопросов не задавать: при неясности выбери простейший безопасный вариант и запиши в %s (раздел «Допущения»)." % report,
        "Репозиторий %s, ветка %s. Работай в ветке %s от свежего main, создай pull request; слияние делает директор." % (repo, branch, pattern),
        "Проект и контракты: " + gdds + " (читать полностью), docs/gdd/DECISIONS_APPROVED.md, docs/AI_RULES.md; макеты в docs/mockups; эталонные данные и тесты проекта читать, не менять.",
        "Зона файлов (только это): " + ", ".join(zone) + ". Общие файлы не менять: " + ", ".join(plan["rules"]["shared_files_director_only"]) + ".",
        "Никаких секретов и личных данных. Новые функции за флагом, по умолчанию ВЫКЛЮЧЕНЫ, если проект их использует.",
    ]
    rules.extend(lane.get("checks", []))
    out = [f"Задание {pid}: {p['title']} (линия {p['lane']}: {lane['name']}, шаг {p['step']}).", "", p["goal"], ""]
    out += ["Правила:"] + [f"{i}. {r}" for i, r in enumerate(rules, 1)]
    out += ["", "Критерии готовности:"] + [f"- {c}" for c in p["done_when"]]
    out += ["", "Сдача: ветка, SHA, PR, список файлов, результаты проверок, раздел «Допущения»."]
    return "\n".join(out)

def main(argv):
    global PLAN, OUT
    if len(argv) > 2 and argv[1] == "--plan":
        PLAN = Path(argv[2]).resolve()
        OUT = PLAN.with_name("WORK_PLAN.md")
        argv = [argv[0]] + argv[3:]
    plan = load()
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "check":
        errs = validate(plan)
        print("\n".join(errs) if errs else f"План в порядке: {len(plan['packages'])} пакетов")
        return 1 if errs else 0
    if cmd == "render":
        OUT.write_text(render(plan), encoding="utf-8")
        print(f"{OUT.relative_to(ROOT) if OUT.is_relative_to(ROOT) else OUT} обновлён")
        return 0
    if cmd == "next":
        r = ready(plan)
        for lane in plan["lanes"]:
            items = [p for p in r if p["lane"] == lane]
            print(f"Линия {lane}: " + (", ".join(f"{p['id']} {p['title']}" for p in items) if items else "нет готовых пакетов"))
        return 0
    if cmd == "prompt":
        print(prompt(plan, argv[2]))
        return 0
    if cmd == "set":
        pid, st = argv[2], argv[3]
        if st not in STATUSES:
            print("статус: planned|wip|done")
            return 1
        next(p for p in plan["packages"] if p["id"] == pid)["status"] = st
        save(plan)
        OUT.write_text(render(plan), encoding="utf-8")
        print(f"{pid} -> {st}")
        return 0
    print(__doc__)
    return 1

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
