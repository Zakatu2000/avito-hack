"""Typed action tools: preview -> human confirm -> execute exactly once -> audit.

The LLM/agent layer NEVER writes here directly. Every side effect is a typed
tool call with: JSON payload contract, server-built preview, explicit user
confirmation token, idempotency key (one execution per key), and an
append-only audit trail. Integrations are local mock adapters ([DEMO MOCK])
with the same contracts a live adapter would implement.
"""
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone

TOOL_CONTRACTS = {
    "send_message": {
        "label": "Сообщение куратору/бадди",
        "adapter": "messenger",
        "fields": {"to": str, "subject": str, "body": str},
        "demo": True,
    },
    "access_request": {
        "label": "Заявка на доступ",
        "adapter": "access_portal",
        "fields": {"resource": str, "justification": str, "approver": str},
        "demo": True,
    },
    "reminder": {
        "label": "Напоминание",
        "adapter": "calendar",
        "fields": {"text": str, "whenLabel": str},
        "demo": True,
    },
    "meeting": {
        "label": "Встреча 1:1 / подготовка",
        "adapter": "calendar",
        "fields": {"title": str, "withWhom": str, "whenLabel": str, "agenda": str},
        "demo": True,
    },
    "checklist_evidence": {
        "label": "Отметка пункта чек-листа",
        "adapter": "checklist",
        "fields": {"itemId": str, "evidenceUri": str, "note": str},
        "demo": True,
    },
    "escalation": {
        "label": "Эскалация человеку",
        "adapter": "messenger",
        "fields": {"severity": str, "to": str, "summary": str},
        "demo": True,
    },
    "development_plan": {
        "label": "План развития куратору",
        "adapter": "messenger",
        "fields": {"to": str, "subject": str, "body": str, "assessmentId": str},
        "demo": True,
    },
}

# Recipient allowlist: the mock messenger only delivers inside the demo org.
ALLOWED_RECIPIENTS = ("mentor", "curator", "buddy", "hr", "support")

SECRET_PATTERNS = (
    re.compile(r"ghp_[0-9a-zA-Z]{10,}"),
    re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"),
    re.compile(r"Bearer\s+[0-9a-zA-Z._-]{12,}", re.IGNORECASE),
    re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+"),
)


class ActionError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def contains_secret(payload):
    text = json.dumps(payload, ensure_ascii=False)
    return any(p.search(text) for p in SECRET_PATTERNS)


def validate_payload(action_type, payload):
    contract = TOOL_CONTRACTS.get(action_type)
    if contract is None:
        raise ActionError(400, "invalid_input", "Неизвестный тип действия")
    if not isinstance(payload, dict):
        raise ActionError(400, "invalid_input", "Проверьте ввод")
    fields = contract["fields"]
    if set(payload) != set(fields):
        raise ActionError(400, "invalid_input",
                          f"Поля действия: {', '.join(sorted(fields))}")
    for name, ftype in fields.items():
        if not isinstance(payload[name], ftype) or (
                ftype is str and not payload[name].strip()):
            raise ActionError(400, "invalid_input", "Проверьте ввод")
        if ftype is str and len(payload[name]) > 4000:
            raise ActionError(400, "invalid_input", "Слишком длинный текст")
    if action_type in ("send_message", "development_plan"):
        if payload["to"] not in ALLOWED_RECIPIENTS:
            raise ActionError(403, "forbidden", "Получатель вне разрешённого списка демо")
    if action_type == "escalation" and payload["severity"] not in (
            "blocker", "urgent", "sensitive"):
        raise ActionError(400, "invalid_input", "severity: blocker|urgent|sensitive")
    if contains_secret(payload):
        raise ActionError(400, "invalid_input",
                          "Похоже на секрет — удалите токены/пароли из текста")
    return contract


def idempotency_key(user_id, action_type, payload):
    raw = json.dumps([user_id, action_type, payload], ensure_ascii=False,
                     sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _audit(cur, user_id, action_id, event, payload=None):
    cur.execute(
        "INSERT INTO action_audit (user_id, action_id, event, payload) "
        "VALUES (%s, %s, %s, %s)",
        (user_id, action_id, event, json.dumps(payload or {}, ensure_ascii=False)))


def _row_to_preview(row):
    contract = TOOL_CONTRACTS[row["action_type"]]
    return {
        "actionId": row["id"],
        "actionType": row["action_type"],
        "label": contract["label"],
        "payload": row["payload"],
        "idempotencyKey": row["idempotency_key"],
        "confirmationToken": row["confirmation_token"],
        "status": row["status"],
        "checklistItemId": row["checklist_item_id"],
        "result": row["result"],
        "demo": contract["demo"],
        "createdAt": row["created_at"].isoformat(),
    }


def create_preview(cur, user_id, action_type, payload, *, checklist_item_id=None):
    contract = validate_payload(action_type, payload)
    key = idempotency_key(user_id, action_type, payload)
    existing = cur.execute(
        "SELECT * FROM pending_actions WHERE user_id = %s AND idempotency_key = %s "
        "AND status <> 'cancelled'", (user_id, key)).fetchone()
    if existing is not None:
        # Same content -> same preview; never a second record for one intent.
        return _row_to_preview(existing), True
    action_id = "act-" + secrets.token_hex(6)
    token = secrets.token_urlsafe(18)
    cur.execute(
        "INSERT INTO pending_actions "
        "(id, user_id, action_type, payload, checklist_item_id, "
        " idempotency_key, confirmation_token, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft_preview')",
        (action_id, user_id, action_type, json.dumps(payload, ensure_ascii=False),
         checklist_item_id, key, token))
    _audit(cur, user_id, action_id, "preview_created",
           {"actionType": action_type, "idempotencyKey": key})
    row = cur.execute("SELECT * FROM pending_actions WHERE id = %s",
                      (action_id,)).fetchone()
    return _row_to_preview(row), False


def cancel_action(cur, user_id, action_id):
    row = cur.execute(
        "SELECT * FROM pending_actions WHERE id = %s AND user_id = %s",
        (action_id, user_id)).fetchone()
    if row is None:
        raise ActionError(403, "forbidden", "Действие недоступно")
    if row["status"] != "draft_preview":
        raise ActionError(409, "conflict", "Отменить можно только черновик")
    cur.execute("UPDATE pending_actions SET status = 'cancelled', "
                "updated_at = now() WHERE id = %s", (action_id,))
    _audit(cur, user_id, action_id, "cancelled")
    return {"cancelled": True, "actionId": action_id}


def _execute_mock(cur, user_id, row):
    """Local mock adapters. Deterministic ids; writes stay inside demo tables."""
    action_type = row["action_type"]
    payload = row["payload"]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if action_type in ("send_message", "escalation", "development_plan"):
        cur.execute(
            "INSERT INTO curator_messages (user_id, direction, channel, body) "
            "VALUES (%s, 'out', %s, %s)",
            (user_id, payload.get("to", "curator"),
             payload.get("body") or payload.get("summary", "")))
        msg_id = cur.execute(
            "SELECT max(id) AS id FROM curator_messages WHERE user_id = %s",
            (user_id,)).fetchone()["id"]
        return {"ticket": f"MSG-{msg_id:05d}", "sentAt": stamp,
                "channel": payload.get("to", "curator"), "mock": True}
    if action_type == "access_request":
        digest = hashlib.sha256(
            f"{user_id}:{payload['resource']}".encode()).hexdigest()[:6].upper()
        return {"ticket": f"ACC-2026-{digest}", "submittedAt": stamp,
                "resource": payload["resource"], "approver": payload["approver"],
                "mock": True}
    if action_type in ("reminder", "meeting"):
        return {"event": f"CAL-{secrets.token_hex(3).upper()}",
                "scheduledAt": stamp, "mock": True}
    if action_type == "checklist_evidence":
        return {"recorded": True, "itemId": payload["itemId"], "at": stamp,
                "mock": True}
    raise ActionError(400, "invalid_input", "Неизвестный тип действия")


def confirm_action(cur, user_id, action_id, token, client_key=None):
    """Execute exactly once per idempotency key. Safe to retry with the same
    confirmation token and client key: the first result is replayed."""
    row = cur.execute(
        "SELECT * FROM pending_actions WHERE id = %s AND user_id = %s "
        "FOR UPDATE", (action_id, user_id)).fetchone()
    if row is None:
        raise ActionError(403, "forbidden", "Действие недоступно")
    if token != row["confirmation_token"]:
        raise ActionError(403, "forbidden", "Недействительный токен подтверждения")
    if row["status"] == "executed":
        _audit(cur, user_id, action_id, "idempotent_replay",
               {"clientKey": client_key})
        return {**_row_to_preview(row), "idempotentReplay": True}
    if row["status"] != "draft_preview":
        raise ActionError(409, "conflict", "Действие уже обработано")
    try:
        result = _execute_mock(cur, user_id, row)
    except ActionError:
        cur.execute("UPDATE pending_actions SET status = 'failed', "
                    "updated_at = now() WHERE id = %s", (action_id,))
        _audit(cur, user_id, action_id, "execution_failed")
        raise
    cur.execute("UPDATE pending_actions SET status = 'executed', result = %s, "
                "updated_at = now() WHERE id = %s",
                (json.dumps(result, ensure_ascii=False), action_id))
    _audit(cur, user_id, action_id, "executed", {"result": result,
                                                 "clientKey": client_key})
    row = cur.execute("SELECT * FROM pending_actions WHERE id = %s",
                      (action_id,)).fetchone()
    return {**_row_to_preview(row), "idempotentReplay": False}


def list_actions(cur, user_id, limit=20):
    rows = cur.execute(
        "SELECT * FROM pending_actions WHERE user_id = %s "
        "ORDER BY created_at DESC, id DESC LIMIT %s", (user_id, limit)).fetchall()
    return [_row_to_preview(r) for r in rows]


def audit_log(cur, user_id, limit=30):
    rows = cur.execute(
        "SELECT id, action_id, event, payload, created_at FROM action_audit "
        "WHERE user_id = %s ORDER BY id DESC LIMIT %s", (user_id, limit)).fetchall()
    return [{"id": r["id"], "actionId": r["action_id"], "event": r["event"],
             "payload": r["payload"], "at": r["created_at"].isoformat()}
            for r in rows]
