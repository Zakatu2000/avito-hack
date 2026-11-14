"""Frontend contract adapter. Durable requests, role checks and local demo grants."""
import json
import secrets
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Blueprint, g, jsonify, request

from ai.buddy_intents import classify
from server import knowledge, onboarding, orchestrator
from server.portal_auth import current_account, public_user

FIXTURES = Path(__file__).with_name("portal_fixtures")


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text(encoding="utf-8"))


class PortalError(Exception):
    def __init__(self, status, message, code="BAD_REQUEST"):
        self.status, self.message, self.code = status, message, code


def checklist(conn, user_id):
    states = {r["item_id"]: r["status"] for r in conn.execute(
        "SELECT item_id,status FROM portal_progress WHERE user_id=%s", (user_id,))}
    stages = fixture("checklist")
    for stage in stages:
        for item in stage["items"]:
            item["status"] = states.get(item["id"], "not_started")
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


def validate_payload(kind, data):
    fields = {"startDate", "endDate", "reason", "comment", "saveDraft"} if kind == "leave" else {
        "system", "justification", "durationDays", "saveDraft"}
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
            conn.execute("INSERT INTO portal_progress VALUES (%s,%s,%s) ON CONFLICT(user_id,item_id) DO UPDATE SET status=EXCLUDED.status",
                         (g.account["user_id"], item_id, data["status"]))
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
            conn.execute("UPDATE portal_progress SET status='done' WHERE user_id=%s AND item_id=%s", (data["userId"], item_id))
            return jsonify(pending_items(conn))

    @bp.get("/api/requests")
    def list_requests():
        queue = request.args.get("scope") == "queue"
        if queue:
            require_approver()
        with connect() as conn:
            rows = conn.execute("SELECT r.data FROM portal_requests r JOIN portal_accounts a ON a.user_id=r.user_id "
                                "WHERE a.team=%s AND (%s OR r.user_id=%s) ORDER BY r.created_at DESC",
                                (g.account["team"], g.account["role"] in ("mentor", "lead"), g.account["user_id"]))
            return jsonify([r["data"] for r in rows if not queue or r["data"]["status"] in ("sent", "approving")])

    @bp.post("/api/requests/<kind>")
    def create_request(kind):
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
            conn.execute("INSERT INTO portal_requests(id,user_id,status,data) VALUES (%s,%s,%s,%s)",
                         (ticket["id"], g.account["user_id"], status, json.dumps(ticket)))
        return jsonify(ticket), 201

    @bp.post("/api/requests/<request_id>/<operation>")
    def change_request(request_id, operation):
        if operation not in ("send", "approve", "reject"):
            raise PortalError(404, "Операция не найдена", "NOT_FOUND")
        if operation != "send":
            require_approver()
        data = body() if request.content_length else {}
        if (operation == "reject" and (not set(data) <= {"comment"} or not isinstance(data.get("comment", ""), str) or len(data.get("comment", "")) > 300)) or (operation != "reject" and data):
            raise PortalError(400, "Некорректные поля операции")
        with connect() as conn:
            row = conn.execute("SELECT r.* FROM portal_requests r JOIN portal_accounts a ON a.user_id=r.user_id "
                               "WHERE r.id=%s AND a.team=%s FOR UPDATE OF r", (request_id, g.account["team"])).fetchone()
            if not row or (operation == "send" and row["user_id"] != g.account["user_id"]):
                raise PortalError(404, "Запрос не найден", "NOT_FOUND")
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
            ticket["status"] = target
            ticket["updatedAt"] = datetime.now(timezone.utc).isoformat()
            label = {"sent": "Отправлен", "approving": "На согласовании", "approved": "Выдан" if ticket["kind"] == "access" else "Одобрен", "rejected": "Отклонён"}[target]
            ticket["history"].append(dict(at=ticket["updatedAt"], status=label, by=g.account["name"], **data))
            conn.execute("UPDATE portal_requests SET status=%s,data=%s WHERE id=%s", (target, json.dumps(ticket), request_id))
            return jsonify(ticket)

    @bp.get("/api/contacts")
    def contacts():
        return jsonify(fixture("contacts"))

    @bp.get("/api/kb")
    def kb():
        return jsonify(fixture("kb-articles"))

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
                next_item = next((i for i in items if i["status"] != "done"), None)
                result.append(dict(user=public_user(account), progress=dict(done=done, total=len(items), percent=round(100 * done / len(items)) if items else 0), nextStepTitle=next_item["title"] if next_item else None))
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

    @bp.post("/api/chat")
    def chat():
        data = body()
        if set(data) != {"message"} or not isinstance(data["message"], str) or not 1 <= len(data["message"].strip()) <= 4000:
            raise PortalError(400, "Сообщение должно содержать от 1 до 4000 символов")
        text = data["message"].strip()
        intent = classify(text)
        link, label = "/timeline", "Открыть путь адаптации"
        with connect() as conn:
            items = flat(checklist(conn, g.account["user_id"]))
            completed = sum(i["status"] == "done" for i in items)
            next_item = next((i for i in items if i["status"] != "done"), None)
            sources = []
            if intent == "unsafe":
                answer = "Не передавайте пароли и токены. Я помогаю с адаптацией; права и действия проверяет сервер."
            elif "отгул" in text.lower() or "отпуск" in text.lower():
                answer, link, label = "Оформите даты и причину в форме отгула и подтвердите отправку.", "/requests/new/leave", "Оформить отгул"
            elif intent == "access":
                answer, link, label = "Выберите систему, срок и обоснование в форме доступа. Отправка требует вашего подтверждения.", "/requests/new/access", "Запросить доступ"
            elif intent == "progress":
                answer = f"Выполнено {completed} из {len(items)} пунктов адаптации."
            elif intent == "next_step":
                answer = "Следующий шаг: " + next_item["title"] if next_item else "Все пункты адаптации выполнены."
            elif intent in ("mentor", "feedback", "curator_reply"):
                answer, link, label = "Обратитесь к наставнику. Опишите задачу, что уже попробовали и где нужна помощь.", "/contacts", "Контакты наставника"
            else:
                profile = onboarding.read_profile(conn.cursor(), g.account["user_id"])
                sources = knowledge.search(conn.cursor(), text, track=profile["track"])
                answer = (sources[0]["snippet"] + "\nИсточник: " + sources[0]["title"]) if sources else "Не нашёл подтверждённой информации. Уточните вопрос или обратитесь к наставнику."
                link, label = "/kb", "Открыть базу знаний"
        # Use the same provider and grounding gates as the source backend.
        payload = dict(intent=intent, text=answer, progress=dict(completed=completed, total=len(items), pct=round(100 * completed / len(items), 1) if items else 0), sources=sources,
                       nextStep=dict(id=next_item["id"], title=next_item["title"]) if next_item else None)
        if llm is not None and sources and intent in orchestrator.STEERABLE:
            llm_request = orchestrator._build_llm_request(text, payload, profile)
            if not llm_slots.acquire(timeout=llm_wait):
                raise PortalError(503, "Помощник перегружен. Повторите позже", "UNAVAILABLE")
            try:
                response = orchestrator.call_provider(llm, llm_request)
            except orchestrator.BuddyProviderUnavailable:
                raise PortalError(503, "Помощник временно недоступен", "UNAVAILABLE") from None
            finally:
                llm_slots.release()
            parsed = orchestrator._parse_llm_output(response.content) if response.finish_reason == "stop" else None
            if parsed and parsed[0] == intent and orchestrator._text_consistent_with_facts(parsed[1], payload):
                ok, _ = orchestrator._validated_source_citations(payload, parsed[2])
                if ok:
                    answer = parsed[1]
        # Revalidate session after a potentially slow provider call.
        with connect() as conn:
            if not current_account(conn):
                raise PortalError(401, "Войдите в аккаунт", "UNAUTHENTICATED")
        return jsonify(intentId=intent, text=answer, actions=[dict(id="open-page", label=label, kind="navigate", target=link)])

    return bp
