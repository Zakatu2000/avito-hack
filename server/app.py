"""B2 demo sessions and read-only, user-scoped workspace API."""
import hashlib
import os
import secrets

import psycopg
from flask import Flask, jsonify, request
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

COOKIE = "buddy_session"
SESSION_SECONDS = 8 * 60 * 60
# Unknown usernames take the same password verification path as known ones.
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32), method="pbkdf2:sha256:600000")


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Both the assignment and the resource's team must be visible to this intern.
VISIBLE_ASSIGNMENT = """
    FROM users u
    JOIN assignments a ON a.user_id = u.id
    JOIN resources r ON r.id = a.resource_id AND r.team_id = u.team_id
"""


def read_resource(conn, user_id, resource_id):
    """Return the visible task referencing this resource, or None (including foreign IDs)."""
    return conn.execute(
        'SELECT a.id AS "taskId", a.title, r.id AS "resourceId" '
        + VISIBLE_ASSIGNMENT
        + " WHERE u.id = %s AND u.role = 'intern' AND r.id = %s",
        (user_id, resource_id),
    ).fetchone()


def read_ticket(conn, user_id, request_id):
    """A foreign ID and an unknown ID have the same result."""
    return conn.execute(
        'SELECT ticket.id AS "requestId", ticket.status AS "requestStatus" '
        + VISIBLE_ASSIGNMENT
        + """
        JOIN access_requests ticket ON ticket.assignment_id = a.id
        WHERE u.id = %s AND u.role = 'intern' AND ticket.id = %s
        """,
        (user_id, request_id),
    ).fetchone()


def read_workspace(conn, user_id):
    """Read the assignment, permitted source, current ticket and actual grant in one snapshot."""
    row = conn.execute(
        """SELECT a.id AS task_id, a.title, r.id AS resource_id,
                  i.id AS source_id, i.excerpt, ticket.id AS request_id, ticket.status,
                  g.user_id IS NOT NULL AS granted """
        + VISIBLE_ASSIGNMENT
        + """
        LEFT JOIN instructions i ON i.id = a.source_id AND i.team_id = u.team_id
        LEFT JOIN access_grants g ON g.user_id = u.id AND g.resource_id = r.id
        LEFT JOIN LATERAL (
            SELECT id, status FROM access_requests
            WHERE assignment_id = a.id ORDER BY created_at DESC, id DESC LIMIT 1
        ) ticket ON true
        WHERE u.id = %s AND u.role = 'intern'
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return dict(task=None, source=None, effectiveAccess="unknown", request=None,
                    nextStep="Уточните назначение первой задачи у наставника")

    ticket = None
    if row["request_id"]:
        ticket = {"requestId": row["request_id"], "requestStatus": row["status"]}
    source = None
    if row["source_id"]:
        source = {"sourceId": row["source_id"], "excerpt": row["excerpt"]}
    if row["granted"]:
        step = "Вернитесь к задаче «" + row["title"] + "»"
    else:
        step = {
            "pending": "Дождитесь согласования",
            "approved": "Дождитесь фактической выдачи права",
            "rejected": "Уточните причину у наставника",
            None: "Спросите помощника о первом шаге",
        }[row["status"]]
    return {
        "task": {"taskId": row["task_id"], "title": row["title"], "resourceId": row["resource_id"]},
        "source": source,
        "effectiveAccess": "granted" if row["granted"] else "missing",
        "request": ticket,
        "nextStep": step,
    }


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(DATABASE_URL=os.environ.get("DATABASE_URL"))
    if config:
        app.config.update(config)
    if not app.config["DATABASE_URL"]:
        raise RuntimeError("Set DATABASE_URL to the demo PostgreSQL database")

    def connect():
        return psycopg.connect(app.config["DATABASE_URL"], row_factory=dict_row)

    def expired():
        return jsonify(code="session_expired", message="Войдите снова"), 401

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(psycopg.OperationalError)
    def unavailable(_error):
        return jsonify(code="unavailable", message="Сервис временно недоступен"), 503

    @app.post("/api/session")
    def login():
        data = request.get_json(silent=True)
        if (not isinstance(data, dict) or set(data) != {"username", "password"}
                or not all(isinstance(value, str) and value and "\x00" not in value
                           for value in data.values())):
            return jsonify(code="invalid_input", message="Проверьте ввод"), 400
        try:
            for value in data.values():
                value.encode("utf-8")
        except UnicodeEncodeError:
            return jsonify(code="invalid_input", message="Проверьте ввод"), 400
        with connect() as conn:
            user = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = %s",
                (data["username"],),
            ).fetchone()
            valid_password = check_password_hash(
                user["password_hash"] if user else DUMMY_HASH, data["password"],
            )
            if not user or not valid_password:
                return expired()
            previous = request.cookies.get(COOKIE)
            if previous:
                conn.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash(previous),))
            token = secrets.token_urlsafe(32)
            conn.execute(
                """INSERT INTO sessions(token_hash, user_id, expires_at)
                   VALUES (%s, %s, now() + make_interval(secs => %s))""",
                (token_hash(token), user["id"], SESSION_SECONDS),
            )
            workspace = read_workspace(conn, user["id"])
        response = jsonify(workspace)
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=request.is_secure, samesite="Strict")
        return response

    @app.get("/api/workspace")
    def workspace():
        token = request.cookies.get(COOKIE)
        if not token:
            return expired()
        with connect() as conn:
            session = conn.execute(
                """SELECT user_id FROM sessions
                   WHERE token_hash = %s AND expires_at > now()""",
                (token_hash(token),),
            ).fetchone()
            if not session:
                return expired()
            return jsonify(read_workspace(conn, session["user_id"]))

    return app
