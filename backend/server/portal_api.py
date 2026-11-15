"""Frontend contract adapter. Durable requests, role checks and local demo grants."""
import json
import re
import secrets
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Blueprint, g, jsonify, request

from server import knowledge, onboarding
from server import portal_adaptation as adaptation
from server import portal_chat, portal_requests
from server.portal_auth import current_account, public_user

FIXTURES = Path(__file__).with_name("portal_fixtures")


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text(encoding="utf-8"))


class PortalError(Exception):
    def __init__(self, status, message, code="BAD_REQUEST"):
        self.status, self.message, self.code = status, message, code


def checklist(conn, user_id):
    states = {r["item_id"]: r for r in conn.execute(
        "SELECT item_id,status,started_at,completed_at FROM portal_progress WHERE user_id=%s", (user_id,))}
    stages = fixture("checklist")
    for stage in stages:
        for item in stage["items"]:
            state = states.get(item["id"])
            item["status"] = state["status"] if state else "not_started"
            for source, target in (("started_at", "startedAt"), ("completed_at", "completedAt")):
                if state and state[source]:
                    item[target] = state[source].isoformat()
    return stages


def flat(stages):
    return [item for stage in stages for item in stage["items"]]


def require_approver():
    if g.account["role"] not in ("mentor", "lead"):
        raise PortalError(403, "Операция доступна наставнику и руководителю", "FORBIDDEN")


def scoped_account(conn, user_id):
    account = conn.execute("SELECT * FROM portal_accounts WHERE user_id=%s AND team=%s",
                           (user_id, g.account["team"])).fetchone()
    if not account:
        raise PortalError(404, "Пользователь не найден", "NOT_FOUND")
    return account


def pending_items(conn):
    result = []
    for account in conn.execute("SELECT * FROM portal_accounts WHERE role='intern' AND team=%s ORDER BY name",
                                (g.account["team"],)).fetchall():
        for item in flat(checklist(conn, account["user_id"])):
            if item["status"] == "pending_approval":
                result.append(dict(userId=account["user_id"], userName=account["name"],
                                   itemId=item["id"], title=item["title"], nextStep=item["nextStep"]))
    return result


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise PortalError(400, "Ожидается JSON-объект")
    return data


_CHAT_ID = re.compile(r"^chat-[0-9a-f]{24}$")
_HISTORY_LIMIT = 10
def _conversation(conn, conversation_id, *, lock=False):
    row = conn.execute(
        "SELECT id, title, created_at, updated_at FROM portal_conversations "
        "WHERE id=%s AND user_id=%s" + (" FOR UPDATE" if lock else ""),
        (conversation_id, g.account["user_id"])).fetchone()
    if not row:
        raise PortalError(404, "Чат не найден", "NOT_FOUND")
    return row


def _public_conversation(row):
    return dict(id=row["id"], title=row["title"],
                createdAt=row["created_at"].isoformat(),
                updatedAt=row["updated_at"].isoformat())


def _save_message(conn, conversation_id, role, text, actions=(), reply=None):
    conn.execute(
        "INSERT INTO portal_messages(conversation_id, role, text, actions, reply) "
        "VALUES (%s, %s, %s, %s, %s)",
        (conversation_id, role, text, json.dumps(list(actions), ensure_ascii=False),
         json.dumps(reply or {}, ensure_ascii=False)))
    conn.execute("UPDATE portal_conversations SET updated_at=now() WHERE id=%s",
                 (conversation_id,))


def _history(conn, conversation_id):
    rows = conn.execute(
        "SELECT role, text FROM (SELECT role, text, id FROM portal_messages "
        "WHERE conversation_id=%s ORDER BY id DESC LIMIT %s) recent ORDER BY id",
        (conversation_id, _HISTORY_LIMIT)).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in rows]


def _title_for(text):
    title = " ".join(text.split())[:60].strip(" .!?")
    return title or "Новый чат"


def validate_payload(kind, data):
    fields = {"startDate", "endDate", "reason", "comment", "saveDraft"} if kind == "leave" else {
        "system", "justification", "durationDays", "saveDraft", "taskId"}
    if not set(data) <= fields or ("saveDraft" in data and type(data["saveDraft"]) is not bool):
        raise PortalError(400, "Некорректные поля формы")
    if kind == "leave":
        try:
            start, end = date.fromisoformat(data["startDate"]), date.fromisoformat(data["endDate"])
            if start.isoformat() != data["startDate"] or end.isoformat() != data["endDate"] or end < start:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise PortalError(400, "Проверьте даты отгула") from None
        if data.get("reason") not in ("vacation", "sick", "personal", "other") or not isinstance(data.get("comment", ""), str) or len(data.get("comment", "")) > 300:
            raise PortalError(400, "Проверьте причину и комментарий")
    else:
        if data.get("system") not in [s["id"] for s in fixture("access-systems")]:
            raise PortalError(400, "Неизвестная система")
        if not isinstance(data.get("justification"), str) or not 10 <= len(data["justification"].strip()) <= 300:
            raise PortalError(400, "Обоснование должно содержать от 10 до 300 символов")
        if type(data.get("durationDays")) is not int or not 1 <= data["durationDays"] <= 365:
            raise PortalError(400, "Срок доступа — от 1 до 365 дней")
    return {"kind": kind, **{k: v for k, v in data.items() if k != "saveDraft"}}


def portal_blueprint(connect, ai_mode="demo", llm=None, llm_slots=None, llm_wait=8):
    bp = Blueprint("portal", __name__)

    @bp.before_request
    def authenticate():
        with connect() as conn:
            g.account = current_account(conn)
        if not g.account:
            return jsonify(code="UNAUTHENTICATED", message="Войдите в аккаунт"), 401

    @bp.errorhandler(PortalError)
    def invalid(exc):
        return jsonify(code=exc.code, message=exc.message), exc.status

    @bp.errorhandler(portal_requests.RequestError)
    def request_error(exc):
        return invalid(PortalError(exc.status, str(exc), {
            403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT",
        }.get(exc.status, "BAD_REQUEST")))

    @bp.errorhandler(adaptation.AdaptationConflict)
    def adaptation_error(exc):
        return invalid(PortalError(409, str(exc), "CONFLICT"))

    def current_plan(conn, account=None):
        account = account or g.account
        return adaptation.plan(conn, account, checklist(conn, account["user_id"]))

    def visible_tasks(conn):
        return {x["id"] for x in current_plan(conn)["items"]}

    @bp.get("/api/me")
    def me():
        return jsonify(public_user(g.account))

    @bp.get("/api/users")
    def users():
        require_approver()
        with connect() as conn:
            return jsonify([public_user(a) for a in conn.execute(
                "SELECT * FROM portal_accounts WHERE team=%s ORDER BY name", (g.account["team"],))])

    @bp.get("/api/checklist")
    def get_checklist():
        with connect() as conn:
            return jsonify(checklist(conn, g.account["user_id"]))

    @bp.post("/api/checklist/items/<item_id>/status")
    def update_status(item_id):
        data = body()
        if set(data) != {"status"} or data["status"] not in ("not_started", "in_progress", "pending_approval", "done"):
            raise PortalError(400, "Некорректный статус пункта")
        with connect() as conn:
            conn.execute("SELECT user_id FROM portal_accounts WHERE user_id=%s FOR UPDATE", (g.account["user_id"],))
            items = flat(checklist(conn, g.account["user_id"]))
            item = next((i for i in items if i["id"] == item_id), None)
            if not item:
                raise PortalError(404, "Пункт не найден", "NOT_FOUND")
            allowed = {"not_started": ["in_progress"],
                       "in_progress": ["pending_approval" if item["requiresApproval"] else "done"],
                       "pending_approval": [], "done": []}
            if data["status"] not in allowed[item["status"]]:
                raise PortalError(403, "Этот переход недоступен. Дождитесь подтверждения наставника", "FORBIDDEN")
            if item_id in (adaptation.ACCESS_ITEM, "wk2-env", "wk2-first-task", "m2-solo"):
                step = next(i for i in current_plan(conn)["items"] if i["id"] == item_id)
                blockers = step["blockers"]
                if blockers or item_id == adaptation.ACCESS_ITEM and data["status"] == "done":
                    raise PortalError(409, blockers[0]["reason"] if blockers else "Пункт завершается после выдачи доступов", "CONFLICT")
            conn.execute(
                """INSERT INTO portal_progress(user_id,item_id,status,started_at,completed_at)
                   VALUES (%s,%s,%s,CASE WHEN %s='in_progress' THEN now() END, CASE WHEN %s='done' THEN now() END)
                   ON CONFLICT(user_id,item_id) DO UPDATE SET status=EXCLUDED.status,
                   started_at=COALESCE(portal_progress.started_at,EXCLUDED.started_at),
                   completed_at=EXCLUDED.completed_at""",
                (g.account["user_id"], item_id, data["status"], data["status"], data["status"]),
            )
            adaptation.log_event(conn, g.account["user_id"], "progress_" + data["status"], item_id)
            if item_id == "wk1-team" and data["status"] == "done":
                adaptation.sync_access(conn, g.account["user_id"])
            return jsonify(checklist(conn, g.account["user_id"]))

    @bp.get("/api/pending-items")
    def pending():
        require_approver()
        with connect() as conn:
            return jsonify(pending_items(conn))

    @bp.post("/api/checklist/items/<item_id>/approve")
    def approve_item(item_id):
        require_approver()
        data = body()
        if set(data) != {"userId"} or not isinstance(data["userId"], str):
            raise PortalError(400, "Укажите стажёра")
        with connect() as conn:
            account = scoped_account(conn, data["userId"])
            if account["role"] != "intern":
                raise PortalError(400, "Подтвердить можно пункт стажёра")
            conn.execute("SELECT user_id FROM portal_accounts WHERE user_id=%s FOR UPDATE", (data["userId"],))
            item = next((i for i in flat(checklist(conn, data["userId"])) if i["id"] == item_id), None)
            if not item or item["status"] != "pending_approval":
                raise PortalError(409, "Пункт не ожидает подтверждения", "CONFLICT")
            if item_id in ("wk2-first-task", "m2-solo"):
                step = next(i for i in current_plan(conn, account)["items"] if i["id"] == item_id)
                remaining = [blocker for blocker in step["blockers"] if blocker["action"] != "/contacts"]
                if remaining:
                    raise adaptation.AdaptationConflict(remaining[0]["reason"])
            conn.execute("UPDATE portal_progress SET status='done',completed_at=now() WHERE user_id=%s AND item_id=%s", (data["userId"], item_id))
            adaptation.log_event(conn, data["userId"], "progress_done", item_id)
            if item_id == "wk1-1to1":
                adaptation.sync_access(conn, data["userId"])
            return jsonify(pending_items(conn))

    @bp.get("/api/requests")
    def list_requests():
        queue = request.args.get("scope") == "queue"
        if queue:
            require_approver()
        with connect() as conn:
            rows = conn.execute("SELECT r.* FROM portal_requests r JOIN portal_accounts a ON a.user_id=r.user_id "
                                "WHERE a.team=%s AND (%s OR r.user_id=%s) ORDER BY r.created_at DESC",
                                (g.account["team"], g.account["role"] in ("mentor", "lead"), g.account["user_id"]))
            tickets = []
            for row in rows:
                ticket = portal_requests.public_ticket(row, g.account)
                if ticket["kind"] in portal_requests.NEW_KINDS:
                    if ticket["status"] == "draft" and row["user_id"] != g.account["user_id"]:
                        continue
                    if queue and (not ticket["allowedActions"] or ticket["status"] == "draft" or row["user_id"] == g.account["user_id"]):
                        continue
                elif queue and row["status"] not in ("sent", "approving"):
                    continue
                tickets.append(ticket)
            return jsonify(tickets)

    @bp.post("/api/requests/<kind>")
    def create_request(kind):
        if kind in portal_requests.NEW_KINDS:
            data = body()
            with connect() as conn:
                return jsonify(portal_requests.create(
                    conn, g.account, kind, data, request.headers.get("Idempotency-Key"), visible_tasks(conn),
                )), 201
        if kind not in ("leave", "access"):
            raise PortalError(404, "Операция не найдена", "NOT_FOUND")
        data = body()
        payload = validate_payload(kind, data)
        now = datetime.now(timezone.utc).isoformat()
        status = "draft" if data.get("saveDraft") else "sent"
        ticket = dict(id="req-" + secrets.token_hex(12), kind=kind, authorId=g.account["user_id"],
                      authorName=g.account["name"], status=status, createdAt=now, updatedAt=now,
                      approvers=["Наставник", "Руководитель"], payload=payload,
                      history=[dict(at=now, status="Черновик" if status == "draft" else "Отправлен", by=g.account["name"])])
        with connect() as conn:
            task_id = payload.pop("taskId", None)
            if task_id is not None:
                if not isinstance(task_id, str) or task_id not in visible_tasks(conn):
                    raise PortalError(404, "Пункт адаптации не найден", "NOT_FOUND")
                ticket["taskId"] = task_id
            conn.execute("INSERT INTO portal_requests(id,user_id,status,data,task_id) VALUES (%s,%s,%s,%s,%s)",
                         (ticket["id"], g.account["user_id"], status, json.dumps(ticket), task_id))
            if status == "sent":
                portal_requests.sent_events(conn, ticket)
        return jsonify(ticket), 201

    @bp.post("/api/requests/<request_id>/<operation>")
    def change_request(request_id, operation):
        data = body() if request.get_data(cache=True) else {}
        with connect() as conn:
            author = conn.execute(
                "SELECT r.user_id FROM portal_requests r JOIN portal_accounts a ON a.user_id=r.user_id "
                "WHERE r.id=%s AND a.team=%s", (request_id, g.account["team"]),
            ).fetchone()
            if author:
                adaptation.lock_account(conn, author["user_id"])
            row = conn.execute(
                "SELECT r.* FROM portal_requests r JOIN portal_accounts a ON a.user_id=r.user_id "
                "WHERE r.id=%s AND a.team=%s FOR UPDATE OF r", (request_id, g.account["team"]),
            ).fetchone() if author else None
            if row and row["data"]["kind"] in portal_requests.NEW_KINDS:
                if row["user_id"] != g.account["user_id"] and (row["status"] == "draft" or g.account["role"] == "intern"):
                    raise PortalError(404, "Запрос не найден", "NOT_FOUND")
                version = request.headers.get("X-Request-Version")
                if version is not None and version != row["data"]["updatedAt"]:
                    raise PortalError(409, "Заявка изменилась. Обновите данные.", "CONFLICT")
                return jsonify(portal_requests.change(
                    conn, row, g.account, operation, data, visible_tasks(conn) if operation in ("edit", "send") else set(),
                ))
            if operation not in ("send", "approve", "reject"):
                raise PortalError(404, "Операция не найдена", "NOT_FOUND")
            if operation != "send":
                require_approver()
            if not row or operation == "send" and row["user_id"] != g.account["user_id"]:
                raise PortalError(404, "Запрос не найден", "NOT_FOUND")
            if operation == "reject":
                comment = data.get("comment", "")
                if not set(data) <= {"comment"} or not isinstance(comment, str) or len(comment) > 300:
                    raise PortalError(400, "Некорректные поля операции")
            elif data:
                raise PortalError(400, "Некорректные поля операции")
            ticket = row["data"]
            status = row["status"]
            if operation == "send":
                if status != "draft":
                    raise PortalError(409, "Отправить можно только черновик", "CONFLICT")
                target = "sent"
            else:
                if status not in ("sent", "approving"):
                    raise PortalError(409, "Запрос не ожидает согласования", "CONFLICT")
                target = "rejected" if operation == "reject" else ("approving" if status == "sent" else "approved")
            # Local demo grant is recorded atomically before the UI sees «Выдан».
            if target == "approved" and ticket["kind"] == "access":
                conn.execute("INSERT INTO portal_grants(request_id,user_id,system,expires_at) "
                             "VALUES (%s,%s,%s,now()+make_interval(days=>%s))",
                             (request_id, row["user_id"], ticket["payload"]["system"], ticket["payload"]["durationDays"]))
                adaptation.sync_access(conn, row["user_id"])
            if target == "sent":
                portal_requests.sent_events(conn, ticket)
            if target in ("approved", "rejected"):
                adaptation.log_event(conn, row["user_id"], "request_result", request_id)
            ticket["status"] = target
            ticket["updatedAt"] = datetime.now(timezone.utc).isoformat()
            label = {"sent": "Отправлен", "approving": "На согласовании", "approved": "Выдан" if ticket["kind"] == "access" else "Одобрен", "rejected": "Отклонён"}[target]
            ticket["history"].append(dict(at=ticket["updatedAt"], status=label, by=g.account["name"], **data))
            conn.execute("UPDATE portal_requests SET status=%s,data=%s WHERE id=%s", (target, json.dumps(ticket), request_id))
            return jsonify(ticket)

    @bp.get("/api/contacts")
    def contacts():
        directory = {entry["id"]: entry for entry in fixture("contacts")}
        with connect() as conn:
            staff = conn.execute(
                "SELECT user_id,name,role FROM portal_accounts "
                "WHERE team=%s AND role IN ('mentor','lead') "
                "ORDER BY CASE role WHEN 'mentor' THEN 0 ELSE 1 END, name, user_id",
                (g.account["team"],),
            ).fetchall()
        role_labels = {"mentor": "Наставник", "lead": "Руководитель направления"}
        entries = [
            dict(
                id=person["user_id"], name=person["name"], role=role_labels[person["role"]],
                roleKey=person["role"], source="team",
                helpsWith=directory["c-" + person["role"]]["helpsWith"],
                tone=directory["c-" + person["role"]]["tone"],
                channel="Очередь команды в портале", responseTime="",
            )
            for person in staff
        ]
        entries.extend(
            dict(directory["c-" + role], roleKey=role, source="demo", responseTime="")
            for role in ("hr", "curator")
        )
        return jsonify(entries)

    @bp.get("/api/kb")
    def kb():
        return jsonify(fixture("kb-articles"))

    @bp.get("/api/kb/search")
    def kb_search():
        q = request.args.get("q", "")
        category = request.args.get("category")
        task_id = request.args.get("taskId")
        track = request.args.get("track")
        if len(q) > 500 or (category and category not in knowledge.TIER_BY_SOURCE_TYPE) or (track and track not in knowledge.TRACKS):
            raise PortalError(400, "Проверьте фильтры поиска")
        with connect() as conn:
            facts = current_plan(conn)
            item = next((i for i in facts["items"] if i["id"] == task_id), None)
            if task_id and item is None:
                raise PortalError(404, "Пункт адаптации не найден", "NOT_FOUND")
            effective_track = facts["track"]
            if track and track != effective_track:
                return jsonify([])
            refs = item.get("catalogIds", [task_id]) if item else [None]
            hits = []
            for ref in refs:
                hits.extend(knowledge.search(
                    conn.cursor(), q, track=effective_track, role=g.account["role"],
                    category=category, task_id=ref, limit=12,
                ))
            hits = {hit["chunkId"]: hit for hit in hits}
            return jsonify(sorted(hits.values(), key=lambda hit: (-hit["score"], hit["chunkId"]))[:12])

    @bp.get("/api/adaptation/plan")
    def get_plan():
        with connect() as conn:
            return jsonify(current_plan(conn))

    @bp.post("/api/adaptation/items/<item_id>/transition")
    def change_catalog_item(item_id):
        data = body()
        if g.account["role"] != "intern":
            raise PortalError(403, "Действие доступно стажёру", "FORBIDDEN")
        if not set(data) <= {"target", "evidenceUri"} or data.get("target") not in ("in_progress", "evidence_pending", "completed"):
            raise PortalError(400, "Проверьте переход")
        evidence = data.get("evidenceUri")
        if evidence is not None and (not isinstance(evidence, str) or not evidence.startswith("https://") or len(evidence) > 500):
            raise PortalError(400, "Укажите HTTPS-ссылку на подтверждение")
        with connect() as conn:
            user_id = g.account["user_id"]
            adaptation.lock_account(conn, user_id)
            item = next((i for i in current_plan(conn)["items"] if i["id"] == item_id and i["origin"] == "catalog"), None)
            if not item:
                raise PortalError(404, "Пункт адаптации не найден", "NOT_FOUND")
            if item["blockers"]:
                raise adaptation.AdaptationConflict(item["blockers"][0]["reason"])
            profile = onboarding.read_profile(conn.cursor(), user_id)
            _, error = onboarding.transition(conn.cursor(), user_id, profile, item_id, data["target"], evidence_uri=evidence)
            if error:
                code, message = error
                raise PortalError(403 if code == "forbidden" else 409, message, code.upper())
            adaptation.log_event(conn, user_id, "catalog_" + data["target"], item_id)
            return jsonify(current_plan(conn))

    @bp.post("/api/adaptation/first-task/<operation>")
    def change_first_task(operation):
        if operation not in ("open", "start", "assign", "confirm"):
            raise PortalError(404, "Операция не найдена", "NOT_FOUND")
        data = body() if request.get_data(cache=True) else {}
        with connect() as conn:
            if operation in ("assign", "confirm"):
                require_approver()
                if set(data) != {"userId"} or not isinstance(data["userId"], str):
                    raise PortalError(400, "Укажите стажёра")
                account = scoped_account(conn, data["userId"])
                if account["role"] != "intern":
                    raise PortalError(400, "Действие доступно для стажёра")
            else:
                if data or g.account["role"] != "intern":
                    raise PortalError(403, "Действие доступно владельцу задачи", "FORBIDDEN")
                account = g.account
            user_id = account["user_id"]
            if operation == "assign":
                adaptation.lock_account(conn, user_id)
                profile = onboarding.read_profile(conn.cursor(), user_id)
                code = adaptation.TASKS[profile["track"] if profile else "backend"][0]
                new = conn.execute(
                    "INSERT INTO portal_first_tasks(user_id,task_code,assigned_by) VALUES (%s,%s,%s) "
                    "ON CONFLICT DO NOTHING RETURNING user_id", (user_id, code, g.account["user_id"]),
                ).fetchone()
                if not new:
                    raise adaptation.AdaptationConflict("Учебная задача уже назначена")
                adaptation.log_event(conn, user_id, "task_assigned", code)
                return jsonify(ok=True)
            return jsonify(adaptation.change_first_task(conn, account, checklist(conn, user_id), operation))

    @bp.get("/api/adaptation/metrics")
    def get_adaptation_metrics():
        with connect() as conn:
            accounts = conn.execute(
                "SELECT * FROM portal_accounts WHERE team=%s AND role='intern' AND (%s OR user_id=%s)",
                (g.account["team"], g.account["role"] != "intern", g.account["user_id"]),
            ).fetchall()
            starts = {}
            quick = []
            for account in accounts:
                user_id = account["user_id"]
                profile = onboarding.read_profile(conn.cursor(), user_id)
                if profile:
                    starts[user_id] = profile["start_date"]
                steps = current_plan(conn, account)["quickStart"]
                quick.append(sum(step["done"] for step in steps) / len(steps))
            events = conn.execute(
                "SELECT * FROM portal_events WHERE user_id=ANY(%s)", ([a["user_id"] for a in accounts],),
            ).fetchall()
            return jsonify(adaptation.calculate_metrics(events, starts, quick))

    @bp.get("/api/access-systems")
    def systems():
        return jsonify(fixture("access-systems"))

    @bp.get("/api/interns")
    def interns():
        require_approver()
        with connect() as conn:
            result = []
            for account in conn.execute("SELECT * FROM portal_accounts WHERE role='intern' AND team=%s ORDER BY name", (g.account["team"],)).fetchall():
                items = flat(checklist(conn, account["user_id"]))
                done = sum(i["status"] == "done" for i in items)
                next_item = current_plan(conn, account)["nextStep"]
                task = adaptation.first_task(conn, account["user_id"])
                result.append(dict(user=public_user(account), progress=dict(done=done, total=len(items), percent=round(100 * done / len(items)) if items else 0),
                                   nextStepTitle=next_item["title"] if next_item else None,
                                   firstTaskStatus=("confirmed" if task["start_confirmed_at"] else "reported" if task["start_reported_at"] else "assigned") if task else "unassigned"))
            return jsonify(result)

    @bp.get("/api/metrics")
    def metrics():
        # No fabricated savings: measurements require an actual baseline.
        with connect() as conn:
            accounts = conn.execute("SELECT user_id FROM portal_accounts WHERE role='intern' AND team=%s", (g.account["team"],)).fetchall()
            done = sum(any(i["status"] == "done" for i in flat(checklist(conn, a["user_id"]))) for a in accounts)
        return jsonify(mentorHoursSaved=dict(baseline=dict(min=0, max=0), target=dict(min=0, max=0), current=0),
                       questionsWithoutMentorShare=0, timeToFirstTaskDays=dict(before=0, current=0),
                       internsOnTrackShare=done / len(accounts) if accounts else 0)

    @bp.get("/api/chat/config")
    def chat_config():
        return jsonify(aiMode=ai_mode)

    @bp.get("/api/chats")
    def list_chats():
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM portal_conversations "
                "WHERE user_id=%s ORDER BY updated_at DESC", (g.account["user_id"],)).fetchall()
            return jsonify([_public_conversation(r) for r in rows])

    @bp.post("/api/chats")
    def create_chat():
        data = request.get_json(silent=True)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise PortalError(400, "Ожидается JSON-объект")
        if not set(data) <= {"title"}:
            raise PortalError(400, "Некорректные поля")
        title = data.get("title") or "Новый чат"
        if (not isinstance(title, str) or "\x00" in title
                or not 1 <= len(title.strip()) <= 120):
            raise PortalError(400, "Название чата — от 1 до 120 символов")
        chat_id = "chat-" + secrets.token_hex(12)
        with connect() as conn:
            conn.execute(
                "INSERT INTO portal_conversations(id, user_id, title) VALUES (%s, %s, %s)",
                (chat_id, g.account["user_id"], title.strip()))
            row = _conversation(conn, chat_id)
            return jsonify(_public_conversation(row)), 201

    @bp.delete("/api/chats/<chat_id>")
    def delete_chat(chat_id):
        with connect() as conn:
            _conversation(conn, chat_id)
            conn.execute("DELETE FROM portal_conversations WHERE id=%s", (chat_id,))
            return "", 204

    @bp.get("/api/chats/<chat_id>/messages")
    def chat_messages(chat_id):
        with connect() as conn:
            _conversation(conn, chat_id)
            rows = conn.execute(
                "SELECT id, role, text, actions, reply FROM portal_messages "
                "WHERE conversation_id=%s ORDER BY id", (chat_id,)).fetchall()
            feedback = {row["entity_id"]: row["event_type"].removeprefix("chat_") for row in conn.execute(
                "SELECT entity_id, event_type FROM portal_events WHERE user_id=%s "
                "AND entity_id = ANY(%s) AND event_type IN ('chat_resolved','chat_mentor')",
                (g.account["user_id"], [row["reply"]["messageId"] for row in rows if row["reply"].get("messageId")]),
            )}
            return jsonify([dict(id=row["id"], role=row["role"], text=row["text"], actions=row["actions"],
                                 **row["reply"], **({"feedback": feedback[row["reply"]["messageId"]]}
                                     if row["reply"].get("messageId") in feedback else {})) for row in rows])

    @bp.post("/api/chat")
    def chat():
        data = body()
        text, task_id = data.get("message"), data.get("taskId")
        message_id, chat_id = data.get("messageId"), data.get("conversationId")
        if (not set(data) <= {"message", "taskId", "messageId", "conversationId"}
                or not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000 or "\x00" in text
                or (task_id is not None and (not isinstance(task_id, str) or len(task_id) > 64))
                or (message_id is not None and not portal_chat.valid_message_id(message_id))
                or (chat_id is not None and (not isinstance(chat_id, str) or not _CHAT_ID.fullmatch(chat_id)))):
            raise PortalError(400, "Проверьте сообщение")
        text = text.strip()
        user_id = g.account["user_id"]

        def previous_reply(conn):
            if message_id is None:
                return None
            return conn.execute(
                "SELECT m.text, m.actions, m.reply, m.conversation_id FROM portal_messages m "
                "JOIN portal_conversations c ON c.id=m.conversation_id WHERE c.user_id=%s "
                "AND m.reply->>'messageId'=%s", (user_id, message_id),
            ).fetchone()

        def replay(row):
            if chat_id and chat_id != row["conversation_id"]:
                raise PortalError(409, "Сообщение уже принадлежит другому чату", "CONFLICT")
            return jsonify(text=row["text"], actions=row["actions"],
                           conversationId=row["conversation_id"], **row["reply"])

        with connect() as conn:
            if chat_id:
                _conversation(conn, chat_id)
            previous = previous_reply(conn)
            if previous:
                return replay(previous)
            history = _history(conn, chat_id) if chat_id else []

        reply = portal_chat.respond(
            connect, g.account, text, task_id, history, current_plan,
            lambda conn, uid: flat(checklist(conn, uid)), llm, llm_slots, llm_wait, PortalError,
        )
        unsafe = reply["intentId"] == "unsafe"
        with connect() as conn:
            account = current_account(conn)
            if account is None or account["user_id"] != user_id:
                raise PortalError(401, "Войдите в аккаунт", "UNAUTHENTICATED")
            adaptation.lock_account(conn, user_id)
            previous = previous_reply(conn)
            if previous:
                return replay(previous)
            if chat_id:
                _conversation(conn, chat_id, lock=True)
                if history != _history(conn, chat_id):
                    raise PortalError(409, "История чата изменилась. Повторите запрос.", "CONFLICT")
            else:
                chat_id = "chat-" + secrets.token_hex(12)
                conn.execute(
                    "INSERT INTO portal_conversations(id, user_id, title) VALUES (%s, %s, %s)",
                    (chat_id, user_id, "Новый чат" if unsafe else _title_for(portal_chat._redact_contacts(text))),
                )
            _save_message(conn, chat_id, "user", "[сообщение скрыто проверкой безопасности]" if unsafe else text)
            metadata = {}
            if message_id is not None:
                metadata = dict(intentId=reply["intentId"], aiMode=ai_mode, messageId=message_id,
                                sources=reply["sources"], answerMethod=reply["answerMethod"])
                adaptation.log_event(conn, user_id, "chat_answered", message_id)
            _save_message(conn, chat_id, "bot", reply["text"], reply["actions"], metadata)
        return jsonify({**metadata, "intentId": reply["intentId"], "text": reply["text"],
                        "actions": reply["actions"], "conversationId": chat_id})

    @bp.post("/api/chat/feedback")
    def feedback():
        data = body()
        if set(data) != {"messageId", "outcome"} or not portal_chat.valid_message_id(data["messageId"]) or data["outcome"] not in ("resolved", "mentor"):
            raise PortalError(400, "Проверьте данные отзыва")
        with connect() as conn:
            user_id = g.account["user_id"]
            message_id = data["messageId"]
            adaptation.lock_account(conn, user_id)
            previous = conn.execute(
                "SELECT event_type FROM portal_events WHERE user_id=%s AND entity_id=%s "
                "AND event_type IN ('chat_answered','chat_resolved','chat_mentor')", (user_id, message_id),
            ).fetchall()
            names = {row["event_type"] for row in previous}
            if "chat_answered" not in names:
                raise PortalError(404, "Ответ не найден", "NOT_FOUND")
            target = "chat_" + data["outcome"]
            if target not in names and names & {"chat_resolved", "chat_mentor"}:
                raise adaptation.AdaptationConflict("Отзыв уже сохранён")
            adaptation.log_event(conn, user_id, target, message_id)
            return jsonify(ok=True)

    return bp
