"""Transactional proposal and access-request service for the demo integration."""
import hashlib
import re
from uuid import uuid4

from psycopg.rows import dict_row


KEY_PATTERN = re.compile(r"[!-+\--~]{1,128}")


class AccessError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _lock_assignment(cur, user_id):
    # All confirmations for this user serialize here. The locks also stabilize
    # role, assignment and team visibility until the transaction finishes.
    cur.execute("""
        SELECT a.id, a.version, a.resource_id
        FROM users u
        JOIN assignments a ON a.user_id = u.id
        JOIN resources r ON r.id = a.resource_id AND r.team_id = u.team_id
        WHERE u.id = %s AND u.role = 'intern'
        FOR UPDATE OF u, a FOR SHARE OF r
    """, (user_id,))
    assignment = cur.fetchone()
    if not assignment:
        raise AccessError(403, "Операция недоступна")
    return assignment


def _has_grant(cur, user_id, resource_id):
    cur.execute("SELECT 1 FROM access_grants WHERE user_id = %s AND resource_id = %s",
                (user_id, resource_id))
    return cur.fetchone() is not None


def _active_ticket(cur, user_id, resource_id):
    cur.execute("""
        SELECT id, status, assignment_id FROM access_requests
        WHERE user_id = %s AND resource_id = %s AND status IN ('pending', 'approved')
        FOR UPDATE
    """, (user_id, resource_id))
    return cur.fetchone()


def create_proposal(conn, user_id):
    """Save a scoped suggestion, never create a ticket before confirmation."""
    with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        assignment = _lock_assignment(cur, user_id)
        resource_id = assignment["resource_id"]
        if _has_grant(cur, user_id, resource_id):
            raise AccessError(409, "Доступ уже предоставлен")
        if _active_ticket(cur, user_id, resource_id):
            raise AccessError(409, "Заявка на доступ уже существует")
        proposal_id = "prop-" + uuid4().hex
        cur.execute("""
            INSERT INTO proposals (id, assignment_id, assignment_version, user_id, resource_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (proposal_id, assignment["id"], assignment["version"], user_id, resource_id))
        return {"proposalId": proposal_id, "resourceId": resource_id,
                "summary": "Запросить право чтения учебного репозитория"}


def confirm_proposal(conn, user_id, proposal_id, key):
    """Recheck authorization and atomically store the ticket and retry bindings."""
    if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
        raise AccessError(400, "Проверьте ключ повторной попытки")
    key_hash = hashlib.sha256(key.encode("ascii")).digest()

    with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        assignment = _lock_assignment(cur, user_id)
        cur.execute("""
            SELECT assignment_id, assignment_version, resource_id, request_id
            FROM proposals WHERE id = %s AND user_id = %s FOR UPDATE
        """, (proposal_id, user_id))
        proposal = cur.fetchone()
        if not proposal:
            raise AccessError(403, "Операция недоступна")
        if (proposal["assignment_id"] != assignment["id"]
                or proposal["assignment_version"] != assignment["version"]
                or proposal["resource_id"] != assignment["resource_id"]):
            raise AccessError(409, "Назначение изменилось. Обновите предложение")

        cur.execute("SELECT proposal_id FROM confirmation_keys WHERE user_id = %s AND key_hash = %s",
                    (user_id, key_hash))
        binding = cur.fetchone()
        if binding and binding["proposal_id"] != proposal_id:
            raise AccessError(409, "Ключ уже связан с другим предложением")

        if proposal["request_id"]:
            cur.execute("SELECT id, status FROM access_requests WHERE id = %s FOR SHARE",
                        (proposal["request_id"],))
            ticket = cur.fetchone()
        else:
            if _has_grant(cur, user_id, proposal["resource_id"]):
                raise AccessError(409, "Доступ уже предоставлен")
            ticket = _active_ticket(cur, user_id, proposal["resource_id"])
            if ticket and ticket["assignment_id"] != assignment["id"]:
                raise AccessError(409, "Существует заявка по предыдущему назначению")
            if not ticket:
                cur.execute("""
                    INSERT INTO access_requests (id, assignment_id, status, user_id, resource_id,
                                                 assignment_version)
                    VALUES (%s, %s, 'pending', %s, %s, %s) RETURNING id, status
                """, ("req-" + uuid4().hex, assignment["id"], user_id, proposal["resource_id"],
                      proposal["assignment_version"]))
                ticket = cur.fetchone()
            cur.execute("UPDATE proposals SET request_id = %s WHERE id = %s",
                        (ticket["id"], proposal_id))

        if not binding:
            cur.execute("""
                INSERT INTO confirmation_keys (user_id, key_hash, proposal_id) VALUES (%s, %s, %s)
            """, (user_id, key_hash, proposal_id))
        return {"requestId": ticket["id"], "requestStatus": ticket["status"]}
