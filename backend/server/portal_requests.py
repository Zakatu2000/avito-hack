"""Portal request validation and state transitions."""
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit

from psycopg.types.json import Jsonb

from server import portal_adaptation as adaptation
from server.knowledge import TRACKS

NEW_KINDS = ("technical_support", "mentor_consultation", "learning_request")
CATEGORIES = ("environment", "software", "network", "git", "other")
PRIORITIES = ("low", "normal", "high")
LABELS = {
    "draft": "Черновик", "sent": "Отправлен", "in_progress": "В работе",
    "awaiting_confirmation": "Ожидается ответ стажёра", "scheduled": "Время согласовано",
    "resolved": "Решение предложено", "closed": "Закрыт", "completed": "Завершён",
}


class RequestError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _invalid(message="Некорректные поля формы"):
    raise RequestError(400, message)


def _text(data, name, limit, required=True):
    value = data.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or "\x00" in value or not 1 <= len(value.strip()) <= limit:
        _invalid(f"Проверьте поле {name}")
    return value.strip()


def _date(data, name, future=True):
    value = _text(data, name, 64)
    try:
        parsed = datetime.fromisoformat(value)
        if "T" not in value or parsed.utcoffset() is None:
            raise ValueError()
        utc = parsed.astimezone(timezone.utc)
        if future and utc <= datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError, OverflowError):
        _invalid("Укажите будущие дату и время с часовым поясом")
    return utc.isoformat()


def _link(data):
    value = _text(data, "url", 1000, required=False)
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in value):
            raise ValueError()
    except ValueError:
        _invalid("Укажите корректную HTTPS-ссылку")
    return value


def payload(kind, data, *, draft=False):
    shared = {"taskId", "saveDraft"}
    fields = {
        "technical_support": {"category", "title", "description", "priority"},
        "mentor_consultation": {"topic", "description", "preferredAt"},
        "learning_request": {"topic", "track", "reason"},
    }[kind]
    if not set(data) <= fields | shared or "saveDraft" in data and type(data["saveDraft"]) is not bool:
        _invalid()
    values = {}
    for key in sorted(fields):
        if draft and key not in data:
            continue
        if key == "preferredAt":
            values[key] = _date(data, key, future=not draft)
        else:
            values[key] = _text(data, key, 200 if key in ("title", "topic") else 2000)
    for field, options in (("category", CATEGORIES), ("priority", PRIORITIES), ("track", TRACKS)):
        if field in values and values[field] not in options:
            _invalid(f"Недопустимое значение поля {field}")
    task_id = _text(data, "taskId", 64, required=False)
    return dict(kind=kind, **values, **({"taskId": task_id} if task_id else {}))


def allowed(ticket, actor, assignee_id):
    status = ticket["status"]
    kind = ticket["kind"]
    owner = actor["user_id"] == ticket["authorId"]
    manager = not owner and actor["role"] in ("mentor", "lead")
    mentor = manager and actor["role"] == "mentor"
    assignee = manager and actor["user_id"] == assignee_id
    if status == "draft":
        return ["edit", "send"] if owner else []
    if kind == "technical_support":
        if status == "sent" and manager:
            return ["claim"]
        if status == "in_progress" and assignee:
            return ["resolve"]
        if status == "resolved" and owner:
            return ["close", "reopen"]
    if kind == "mentor_consultation":
        if status == "sent" and mentor and (not assignee_id or assignee):
            return ["schedule", "propose"]
        if status == "awaiting_confirmation" and owner:
            return ["accept", "counter"]
        if status == "scheduled" and assignee:
            return ["complete"]
    if kind == "learning_request" and status == "sent" and mentor:
        return ["recommend"]
    return []


def public_ticket(row, account):
    ticket = row["data"]
    if ticket["kind"] not in NEW_KINDS:
        return ticket
    return {**ticket, "allowedActions": allowed(ticket, account, row["assignee_id"])}


def _check_task(ticket_payload, visible):
    if ticket_payload.get("taskId") and ticket_payload["taskId"] not in visible:
        raise RequestError(404, "Пункт адаптации не найден")


def create(conn, account, kind, data, key, visible):
    if account["role"] != "intern":
        raise RequestError(403, "Создать обращение может стажёр")
    if key is not None and (not 1 <= len(key) <= 128 or not key.isascii() or any(not c.isalnum() and c not in "._-" for c in key)):
        _invalid("Некорректный Idempotency-Key")
    user_id = account["user_id"]
    adaptation.lock_account(conn, user_id)
    fingerprint = dict(kind=kind, **{k: v for k, v in data.items() if k != "kind"})
    if key:
        previous = conn.execute("SELECT * FROM portal_requests WHERE user_id=%s AND idempotency_key=%s",
                                (user_id, key)).fetchone()
        if previous:
            if previous["creation_payload"] != fingerprint:
                raise RequestError(409, "Ключ уже использован для другой заявки")
            return public_ticket(previous, account)
    draft = data.get("saveDraft") is True
    content = payload(kind, data, draft=draft)
    _check_task(content, visible)
    status = "draft" if draft else "sent"
    now = datetime.now(timezone.utc).isoformat()
    ticket_id = "req-" + secrets.token_hex(12)
    ticket = dict(
        id=ticket_id, kind=kind, payload=content, authorId=user_id, authorName=account["name"],
        status=status, createdAt=now, updatedAt=now, approvers=["Наставник", "Руководитель"],
        history=[dict(at=now, status=LABELS[status], by=account["name"])],
        taskId=content.get("taskId"), assignee=None, result=None, scheduledAt=None, proposedAt=None,
    )
    row = conn.execute(
        """INSERT INTO portal_requests(id,user_id,status,data,idempotency_key,creation_payload,task_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (ticket_id, user_id, status, Jsonb(ticket), key, Jsonb(fingerprint) if key else None, ticket["taskId"]),
    ).fetchone()
    if not draft:
        sent_events(conn, ticket)
    return public_ticket(row, account)


def sent_events(conn, ticket):
    adaptation.log_event(conn, ticket["authorId"], "request_sent", ticket["id"])
    if ticket["kind"] == "technical_support" and ticket.get("taskId"):
        adaptation.log_event(conn, ticket["authorId"], "blocker_reported", ticket["id"])


def change(conn, row, account, operation, data, visible):
    if operation not in ("edit", "send", "claim", "resolve", "close", "reopen", "schedule",
                         "propose", "accept", "counter", "complete", "recommend"):
        raise RequestError(404, "Операция не найдена")
    ticket = row["data"]
    owner = ticket["authorId"] == account["user_id"]
    if not owner and (ticket["status"] == "draft" or account["role"] not in ("mentor", "lead")):
        raise RequestError(404, "Запрос не найден")
    if operation not in allowed(ticket, account, row["assignee_id"]):
        if operation in ("edit", "send", "close", "reopen", "accept", "counter") and not owner:
            raise RequestError(403, "Действие доступно автору")
        if operation in ("claim", "resolve", "schedule", "propose", "complete", "recommend") and owner:
            raise RequestError(403, "Действие доступно ответственному")
        raise RequestError(409, "Действие недоступно в текущем состоянии")
    expected = {
        "send": set(), "claim": set(), "resolve": {"result"}, "close": set(), "reopen": {"comment"},
        "schedule": set(), "propose": {"at"}, "counter": {"at"}, "accept": set(),
        "complete": {"result"}, "recommend": {"result", "url"},
    }
    if operation != "edit" and not set(data) <= expected[operation]:
        _invalid()
    assignee = row["assignee_id"]
    status = ticket["status"]
    comment = None
    if operation == "edit":
        ticket["payload"] = payload(ticket["kind"], data, draft=True)
        _check_task(ticket["payload"], visible)
        ticket["taskId"] = ticket["payload"].get("taskId")
    elif operation == "send":
        ticket["payload"] = payload(ticket["kind"], {k: v for k, v in ticket["payload"].items() if k != "kind"})
        _check_task(ticket["payload"], visible)
        status = "sent"
        sent_events(conn, ticket)
    elif operation in ("claim", "schedule", "propose", "recommend"):
        assignee = account["user_id"]
        ticket["assignee"] = dict(id=assignee, name=account["name"])
        status = {"claim": "in_progress", "schedule": "scheduled", "propose": "awaiting_confirmation",
                  "recommend": "resolved"}[operation]
        if operation == "schedule":
            ticket["scheduledAt"] = _date(ticket["payload"], "preferredAt")
        if operation == "propose":
            ticket["proposedAt"] = _date(data, "at")
    elif operation in ("accept", "counter"):
        if operation == "accept":
            ticket["scheduledAt"] = _date(ticket, "proposedAt")
            status = "scheduled"
        else:
            ticket["payload"]["preferredAt"] = _date(data, "at")
            status = "sent"
        ticket["proposedAt"] = None
    else:
        status = {"resolve": "resolved", "close": "closed", "reopen": "in_progress", "complete": "completed"}[operation]
    if operation in ("resolve", "complete", "recommend"):
        comment = _text(data, "result", 2000)
        ticket["result"] = dict(text=comment, url=_link(data) if operation == "recommend" else None)
    if operation == "reopen":
        comment = _text(data, "comment", 1000)
        ticket["result"] = None
    if operation == "close":
        adaptation.log_event(conn, ticket["authorId"], "blocker_closed", ticket["id"])
    if operation in ("close", "complete", "recommend"):
        adaptation.log_event(conn, ticket["authorId"], "request_result", ticket["id"])
    ticket["status"] = status
    ticket["updatedAt"] = datetime.now(timezone.utc).isoformat()
    entry = dict(at=ticket["updatedAt"], by=account["name"], status=LABELS[status])
    if comment:
        entry["comment"] = comment
    if ticket.get("scheduledAt") and operation in ("schedule", "accept"):
        entry["scheduledAt"] = ticket["scheduledAt"]
    if operation == "propose":
        entry["scheduledAt"] = ticket["proposedAt"]
    if operation == "counter":
        entry["scheduledAt"] = ticket["payload"]["preferredAt"]
    ticket["history"].append(entry)
    result = conn.execute(
        "UPDATE portal_requests SET status=%s,data=%s,assignee_id=%s,task_id=%s WHERE id=%s RETURNING *",
        (status, Jsonb(ticket), assignee, ticket["taskId"], ticket["id"]),
    ).fetchone()
    if operation == "close" and ticket.get("taskId") == adaptation.ACCESS_ITEM:
        adaptation.sync_access(conn, ticket["authorId"])
    return public_ticket(result, account)
