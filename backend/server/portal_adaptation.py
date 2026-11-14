"""Portal read model over the team plan and sourced checklist."""
from datetime import date, datetime, time, timezone
from statistics import median
from urllib.parse import urlencode

from psycopg.types.json import Jsonb

from server import onboarding

ACCESS_ITEM = "wk1-access"
FIRST_TASK = "first-task"
SOLO_START = "solo-start"
QUICK = (
    ("team", "Знакомство с командой и наставником", ("wk1-team", "wk1-1to1")),
    ("access", "Критически необходимые доступы", (ACCESS_ITEM,)),
    ("environment", "Настройка рабочего окружения", ("wk2-env",)),
    ("assignment", "Получение и открытие первой задачи", (FIRST_TASK,)),
    ("independent", "Начало самостоятельной работы", (SOLO_START,)),
)
TASKS = {
    "backend": ("starter-backend", "Разобрать тесты учебного сервиса", "Открой README учебного репозитория и найди команду запуска тестов."),
    "analytics": ("starter-analytics", "Проверить учебную выгрузку", "Сверь поля синтетического набора данных с описанием в учебном тикете."),
    "marketing": ("starter-marketing", "Подготовить черновик учебной кампании", "В учебном тикете проверь цель кампании и предложи критерии оценки."),
}
PORTAL_STAGE = {"wk1": 1, "wk2": 2, "m1": 3, "m2": 4, "fin": 6}
# Both team introductions use self-confirmation.
EQUIVALENT_ITEMS = {"common-03": "wk1-team"}
STATUS = {"available": "not_started", "blocked": "not_started",
          "in_progress": "in_progress", "evidence_pending": "pending_approval", "completed": "done"}
ACTIVE_SUPPORT = ("sent", "in_progress", "resolved")


class AdaptationConflict(Exception):
    pass


def url(path, **params):
    return path + "?" + urlencode(params) if params else path


def log_event(conn, user_id, event_type, entity_id, **metadata):
    conn.execute(
        "INSERT INTO portal_events(user_id,event_type,entity_id,metadata) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT DO NOTHING", (user_id, event_type, entity_id, Jsonb(metadata)),
    )


def lock_account(conn, user_id):
    conn.execute("SELECT user_id FROM portal_accounts WHERE user_id=%s FOR UPDATE", (user_id,))


def effective_grants(conn, user_id):
    return {row["system"] for row in conn.execute(
        "SELECT DISTINCT system FROM portal_grants WHERE user_id=%s AND expires_at>now()", (user_id,),
    )}


def access_needed(track):
    return {"confluence", "jira", "repo"} if track == "backend" else {"confluence", "jira"}


def sync_access(conn, user_id):
    profile = onboarding.read_profile(conn.cursor(), user_id)
    if not profile or not access_needed(profile["track"]) <= effective_grants(conn, user_id):
        return
    finished = {row["item_id"] for row in conn.execute(
        "SELECT item_id FROM portal_progress WHERE user_id=%s AND status='done'", (user_id,),
    )}
    equivalent_done = conn.execute(
        "SELECT 1 FROM checklist_state WHERE user_id=%s AND item_id='common-03' AND status='completed'", (user_id,),
    ).fetchone()
    if "wk1-1to1" not in finished or not ("wk1-team" in finished or equivalent_done):
        return
    blocked = conn.execute(
        "SELECT 1 FROM portal_requests WHERE user_id=%s AND task_id=%s "
        "AND data->>'kind'='technical_support' AND status=ANY(%s)",
        (user_id, ACCESS_ITEM, list(ACTIVE_SUPPORT)),
    ).fetchone()
    if blocked:
        return
    changed = conn.execute(
        """INSERT INTO portal_progress(user_id,item_id,status,started_at,completed_at)
           VALUES (%s,%s,'done',now(),now())
           ON CONFLICT(user_id,item_id) DO UPDATE SET status='done', completed_at=now()
           WHERE portal_progress.status <> 'done' RETURNING item_id""", (user_id, ACCESS_ITEM),
    ).fetchone()
    if changed:
        log_event(conn, user_id, "progress_automated", ACCESS_ITEM)


def first_task(conn, user_id):
    return conn.execute("SELECT * FROM portal_first_tasks WHERE user_id=%s", (user_id,)).fetchone()


def _portal_items(stages, by_id, track):
    basic = {item_id: group for group, _, ids in QUICK for item_id in ids}
    prerequisites = {ACCESS_ITEM: ("wk1-team", "wk1-1to1"), "wk2-env": (ACCESS_ITEM,),
                     "wk2-first-task": ("wk2-env", FIRST_TASK), "m2-solo": ("wk2-first-task", SOLO_START)}
    for stage in stages:
        for item in stage["items"]:
            if item["id"] in by_id:
                continue
            item_id = item["id"]
            by_id[item_id] = dict(
                **item, sources=["Программа команды · демо"], origin="portal",
                stage=PORTAL_STAGE[stage["id"]], stageLabel=stage["title"],
                group=basic.get(item_id), priority=10 if item_id in basic else 100,
                dependencies=list(prerequisites.get(item_id, ())),
                requiredAccess=sorted(access_needed(track)) if item_id in (ACCESS_ITEM, "wk2-env", "wk2-first-task", "m2-solo") else [],
                canWork=True, completionCriteria=item["description"],
            )


def _sourced_items(conn, user_id, profile, by_id):
    items, _ = onboarding.read_checklist(conn.cursor(), user_id, profile)
    for item in items:
        item_id = item["id"]
        alias = EQUIVALENT_ITEMS.get(item_id)
        source = item["sourceRef"]
        label = f'{source["sheet"]} · строка {source["row"]}' if "sheet" in source else "Чек-лист"
        if alias in by_id:
            previous = by_id[alias]
            previous["sources"].append(label)
            previous["catalogIds"] = [alias, item_id]
            if STATUS[item["status"]] == "done":
                previous["status"] = "done"
            continue
        by_id[item_id] = dict(
            id=item_id, title=item["title"], description=item["description"],
            nextStep=" ".join(item["instructions"]) or item["description"],
            status=STATUS[item["status"]], requiresApproval=item["completionPolicy"] != "self_confirmed",
            stage=item["stageOrder"], stageLabel=item["stageLabel"], priority=item["priority"],
            group=None, origin="catalog", sources=[label], deadline=None, actionLink=None,
            dependencies=[EQUIVALENT_ITEMS.get(dep, dep) for dep in item["dependencies"]],
            requiredAccess=item["requiredAccess"], estimatedMinutes=item["estimatedMinutes"],
            completionCriteria=item["evidence"] or item["objective"], completionPolicy=item["completionPolicy"],
            startedAt=item["startedAt"], completedAt=item["completedAt"],
            canWork=item["actor"] == "intern" and item["completionPolicy"] != "curator_confirmed",
        )


def _assignment_items(track, assignment, by_id):
    basic = [
        (FIRST_TASK, "Получить и открыть первую задачу", ("wk2-env",),
         "done" if assignment and assignment["opened_at"] else "not_started"),
        (SOLO_START, "Начать самостоятельную работу", (FIRST_TASK,),
         "done" if assignment and assignment["start_confirmed_at"] else
         "pending_approval" if assignment and assignment["start_reported_at"] else "not_started"),
    ]
    for item_id, title, deps, status in basic:
        missing_assignment = item_id == FIRST_TASK and assignment is None
        by_id[item_id] = dict(
            id=item_id, title=title, description="", nextStep=(
                "Открой учебную задачу." if item_id == FIRST_TASK else "Отметь начало работы для подтверждения наставником."
            ), status=status, dependencies=list(deps), requiredAccess=sorted(access_needed(track)),
            stage=2, stageLabel="2-я неделя", priority=10, actionLink=None, deadline=None,
            requiresApproval=item_id == SOLO_START, sources=["Учебная задача · демо"], origin="assignment",
            group="assignment" if item_id == FIRST_TASK else "independent", canWork=not missing_assignment,
        )


def _blockers(item, by_id, grants, tickets):
    item_id = item["id"]
    blockers = []
    missing_dependencies = [by_id[dep]["title"] if dep in by_id else dep
                            for dep in item["dependencies"] if by_id.get(dep, {}).get("status") != "done"]
    if missing_dependencies:
        blockers.append(dict(reason="Сначала выполните: " + ", ".join(missing_dependencies), action="/timeline"))
    for system in sorted(set(item["requiredAccess"]) - grants):
        pending = next((r for r in tickets if r["kind"] == "access" and
                        r["payload"]["system"] == system and r["status"] in ("sent", "approving")), None)
        blockers.append(dict(
            reason=f"Доступ {system} ожидает выдачи" if pending else f"Нет действующего доступа: {system}",
            action="/requests#" + pending["id"] if pending else url("/requests/new/access", system=system, task=item_id),
        ))
    for ticket in tickets:
        if ticket.get("taskId") == item_id and ticket["kind"] == "technical_support" and ticket["status"] in ACTIVE_SUPPORT:
            blockers.append(dict(reason="Техническое обращение ожидает закрытия", action="/requests#" + ticket["id"]))
    if item["status"] == "pending_approval":
        blockers.append(dict(reason="Ожидается подтверждение наставника", action="/contacts"))
    if not item["canWork"]:
        blockers.append(dict(reason="Требуется участие наставника", action=url("/requests/new/mentor_consultation", task=item_id)))
    return blockers


def plan(conn, account, portal_stages):
    user_id = account["user_id"]
    profile = onboarding.read_profile(conn.cursor(), user_id)
    track = profile["track"] if profile else "backend"
    started = profile["start_date"] if profile else date.today()
    week = max(1, (date.today() - started).days // 7 + 1)
    stage_code = onboarding.current_stage_code(week)
    stage_order = onboarding.STAGE_ORDER[stage_code]
    grants = effective_grants(conn, user_id)
    assignment = first_task(conn, user_id)
    tickets = [row["data"] for row in conn.execute(
        "SELECT data FROM portal_requests WHERE user_id=%s AND status<>'draft' ORDER BY created_at,id", (user_id,),
    )]
    by_id = {}
    _portal_items(portal_stages, by_id, track)
    if profile:
        _sourced_items(conn, user_id, profile, by_id)
    _assignment_items(track, assignment, by_id)
    for item in by_id.values():
        item["blockers"] = _blockers(item, by_id, grants, tickets)
        item["requests"] = [dict(id=r["id"], kind=r["kind"], status=r["status"])
                            for r in tickets if r.get("taskId") == item["id"]]
    ordered = sorted(by_id.values(), key=lambda i: (i["stage"], i["priority"], i["id"]))
    quick = [dict(id=group, title=title, items=[by_id[i] for i in ids],
                  done=all(by_id[i]["status"] == "done" and not by_id[i]["blockers"] for i in ids))
             for group, title, ids in QUICK]
    first_open = next((step for step in quick if not step["done"]), None)
    urgent = [] if not first_open else first_open["items"]
    selectable = [i for i in urgent if i["status"] != "done" and not i["blockers"]]
    if not selectable:
        selectable = sorted(
            (i for i in ordered if i["group"] is None and i["status"] != "done" and not i["blockers"] and i["stage"] <= stage_order),
            key=lambda i: (i["priority"], i["stage"], i["id"]),
        )
    relevant = urgent if first_open else [i for i in ordered if i["stage"] <= stage_order and i["status"] != "done"]
    blockers = [dict(**b, itemId=item["id"], title=item["title"]) for item in relevant
                for b in item["blockers"]]
    return dict(track=track, stage=stage_code, quickStart=quick, items=ordered, blockers=blockers,
                nextStep=selectable[0] if selectable else None,
                firstTask=dict(code=assignment["task_code"], opened=bool(assignment["opened_at"]),
                               reported=bool(assignment["start_reported_at"]),
                               confirmed=bool(assignment["start_confirmed_at"])) if assignment else None)


def change_first_task(conn, account, portal_stages, operation):
    user_id = account["user_id"]
    lock_account(conn, user_id)
    data = plan(conn, account, portal_stages)
    assignment = first_task(conn, user_id)
    if not assignment:
        raise AdaptationConflict("Наставник ещё не назначил учебную задачу")
    task_id = FIRST_TASK if operation == "open" else SOLO_START
    step = next(i for i in data["items"] if i["id"] == task_id)
    if operation == "open" and assignment["opened_at"]:
        if step["blockers"]:
            raise AdaptationConflict(step["blockers"][0]["reason"])
    elif operation == "confirm":
        if not assignment["start_reported_at"] or assignment["start_confirmed_at"]:
            raise AdaptationConflict("Старт не ожидает подтверждения")
        remaining = [b for b in step["blockers"] if b["action"] != "/contacts"]
        if remaining:
            raise AdaptationConflict(remaining[0]["reason"])
    elif step["blockers"] or step["status"] == "done":
        raise AdaptationConflict(step["blockers"][0]["reason"] if step["blockers"] else "Действие уже выполнено")
    column = {"open": "opened_at", "start": "start_reported_at", "confirm": "start_confirmed_at"}[operation]
    conn.execute(f"UPDATE portal_first_tasks SET {column}=COALESCE({column},now()) WHERE user_id=%s", (user_id,))
    log_event(conn, user_id, {"open": "task_opened", "start": "start_reported", "confirm": "start_confirmed"}[operation],
              assignment["task_code"])
    if operation == "open":
        code, title, description = TASKS[data["track"]]
        return dict(code=code, title=title, description=description, demo=True)
    return dict(ok=True)


def _measurement(values, reducer):
    return dict(value=round(reducer(values), 2) if values else None, sampleSize=len(values))


def calculate_metrics(events, starts, quick_progress):
    by_entity = {}
    for row in events:
        by_entity.setdefault((row["user_id"], row["entity_id"]), {})[row["event_type"]] = row["occurred_at"]

    def durations(start, end):
        return [(record[end] - record[start]).total_seconds() / 60 for record in by_entity.values()
                if start in record and end in record and record[end] >= record[start]]

    first = []
    for (user_id, _), record in by_entity.items():
        if user_id not in starts or "start_confirmed" not in record or "start_reported" not in record:
            continue
        start = datetime.combine(starts[user_id], time.min, tzinfo=timezone.utc)
        first.append(max(0, (record["start_reported"] - start).total_seconds() / 60))
    reports = [int("chat_resolved" in record) for record in by_entity.values()
               if "chat_resolved" in record or "chat_mentor" in record]
    return dict(
        origin="measured", firstTaskMinutes=_measurement(first, median),
        blockerMinutes=_measurement(durations("blocker_reported", "blocker_closed"), median),
        requestMinutes=_measurement(durations("request_sent", "request_result"), median),
        withoutMentor=_measurement(reports, lambda values: sum(values) / len(values)),
        quickStart=_measurement(quick_progress, lambda values: sum(values) / len(values)),
        manualActionsAvoided=_measurement(
            [1 for record in by_entity.values() if "progress_automated" in record], sum),
    )
