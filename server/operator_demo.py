"""Opt-in simulator for the external approval service. Uses a separate operator session."""
from flask import Blueprint, jsonify, request

from server.access import AccessError
from server.store import reset_demo, is_demo_database


def operator_blueprint(connect, session_user_id, cookie_name):
    demo = Blueprint("demo_operator", __name__, url_prefix="/demo")

    def authorize(conn):
        if not is_demo_database(conn.info.dbname):
            raise AccessError(403, "Демо выключено")
        user = session_user_id(conn, request.cookies.get(cookie_name, ""))
        if not user:
            raise AccessError(401, "Войдите снова")
        operator = conn.execute("""
            SELECT team_id FROM users WHERE id = %s AND role = 'operator' FOR SHARE
        """, (user,)).fetchone()
        if not operator:
            raise AccessError(403, "Операция недоступна")
        return operator["team_id"]

    @demo.route("/requests/<request_id>", methods=["GET", "POST"])
    def inspect_or_update(request_id):
        with connect() as conn:
            team = authorize(conn)
            if "\x00" in request_id:
                raise AccessError(400, "Проверьте ввод")
            ticket = conn.execute("""
                SELECT t.id, t.status, t.user_id, t.resource_id, t.assignment_id
                FROM access_requests t JOIN assignments a ON a.id=t.assignment_id
                JOIN users u ON u.id=t.user_id AND a.user_id=u.id
                JOIN resources r ON r.id=t.resource_id AND r.id=a.resource_id
                WHERE t.id=%s AND u.role='intern' AND u.team_id=%s AND r.team_id=u.team_id
                FOR UPDATE OF u, a, t FOR SHARE OF r
            """, (request_id, team)).fetchone()
            if not ticket:
                raise AccessError(403, "Операция недоступна")
            if request.method == "POST":
                payload = request.get_json(silent=True)
                if not isinstance(payload, dict) or set(payload) != {"action"}:
                    raise AccessError(400, "Проверьте ввод")
                action = payload["action"]
                if action == "grant":
                    if ticket["status"] != "approved":
                        raise AccessError(409, "Сначала одобрите заявку")
                    grant = conn.execute("""INSERT INTO access_grants(user_id,resource_id)
                                    VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING user_id""",
                                 (ticket["user_id"], ticket["resource_id"]))
                    if grant.fetchone():
                        conn.execute("""
                            INSERT INTO onboarding_events(assignment_id,name,request_id)
                            VALUES (%s,'access_granted',%s) ON CONFLICT DO NOTHING
                        """, (ticket["assignment_id"], ticket["id"]))
                elif action in ("approve", "reject"):
                    target = "approved" if action == "approve" else "rejected"
                    if ticket["status"] not in ("pending", target):
                        raise AccessError(409, "Решение уже принято")
                    conn.execute("UPDATE access_requests SET status=%s WHERE id=%s", (target, request_id))
                    ticket["status"] = target
                else:
                    raise AccessError(400, "Проверьте ввод")
            granted = conn.execute("SELECT 1 FROM access_grants WHERE user_id=%s AND resource_id=%s",
                                   (ticket["user_id"],ticket["resource_id"])).fetchone()
            return jsonify(requestId=request_id, requestStatus=ticket["status"],
                           effectiveAccess="granted" if granted else "missing", demo=True)

    @demo.post("/reset")
    def reset():
        with connect() as conn:
            authorize(conn)
            if request.get_json(silent=True) != {"confirm": "reset-demo"}:
                raise AccessError(400, "Подтвердите сброс")
            reset_demo(conn)
        return jsonify(demo=True, reset=True)

    return demo
