"""Session, workspace and access confirmation routes for the synthetic demo."""
import hashlib
import os
import secrets
from pathlib import Path

import psycopg
from flask import Flask, jsonify, request, send_from_directory
from psycopg.rows import dict_row
from werkzeug.utils import import_string
from werkzeug.security import check_password_hash, generate_password_hash

from server.access import AccessError, confirm_proposal, create_proposal
from server.operator_demo import operator_blueprint
from server.dialog import AgentRunner, AgentUnavailable, DemoAgent
from server.buddy_api import buddy_blueprint

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
          AND ticket.user_id = u.id AND ticket.resource_id = r.id
        WHERE u.id = %s AND u.role = 'intern' AND ticket.id = %s
        """,
        (user_id, request_id),
    ).fetchone()


def read_workspace(conn, user_id, request_id=None, *, lock=False):
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
            WHERE assignment_id = a.id AND user_id = u.id AND resource_id = r.id
              AND id = COALESCE(%s::text, id)
            ORDER BY (status IN ('pending', 'approved')) DESC, created_at DESC, id DESC LIMIT 1
        ) ticket ON true
        WHERE u.id = %s AND u.role = 'intern'
        """
        + (" FOR UPDATE OF u, a FOR SHARE OF r" if lock else ""),
        (request_id, user_id),
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
    app.config["DEMO_OPERATOR"] = os.environ.get("BUDDY_DEMO_OPERATOR") == "1"
    if config:
        app.config.update(config)
    if not app.config["DATABASE_URL"]:
        raise RuntimeError("Set DATABASE_URL to the demo PostgreSQL database")

    factory_path = os.environ.get("BUDDY_AGENT_FACTORY")
    agent = app.config.get("AGENT")
    if agent is None and factory_path:
        agent = import_string(factory_path)()
    mode = "live" if agent is not None else "demo"
    timeout = float(app.config.get("AGENT_TIMEOUT", os.environ.get("BUDDY_AGENT_TIMEOUT", "10")))
    if not 0 < timeout <= 65:
        raise ValueError("BUDDY_AGENT_TIMEOUT must be in (0, 65]")
    runner = AgentRunner(agent if agent is not None else DemoAgent(), timeout, mode)

    def connect():
        return psycopg.connect(app.config["DATABASE_URL"], row_factory=dict_row)

    def session_user_id(conn, token):
        session = conn.execute(
            """SELECT user_id FROM sessions
               WHERE token_hash = %s AND expires_at > now()""",
            (token_hash(token),),
        ).fetchone()
        return session["user_id"] if session else None

    def expired():
        return jsonify(code="session_expired", message="Войдите снова"), 401

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(psycopg.OperationalError)
    def unavailable(_error):
        return jsonify(code="unavailable", message="Сервис временно недоступен"), 503

    @app.errorhandler(AccessError)
    def access_error(error):
        code, message = {
            401: ("session_expired", "Войдите снова"),
            400: ("invalid_input", "Проверьте ввод"),
            403: ("forbidden", "Операция недоступна"),
            409: ("conflict", "Обновите состояние"),
        }[error.status_code]
        return jsonify(code=code, message=message), error.status_code

    web_build = Path(__file__).resolve().parents[1] / "web" / "dist"
    if web_build.is_dir():
        @app.get("/")
        def index():
            return send_from_directory(web_build, "index.html")

        @app.get("/assets/<path:filename>")
        def assets(filename):
            return send_from_directory(web_build / "assets", filename)

    @app.get("/health")
    def health():
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return jsonify(status="ok")

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

    @app.route("/api/session", methods=["GET", "DELETE"])
    def current_session():
        token = request.cookies.get(COOKIE)
        if not token:
            return expired()
        with connect() as conn:
            user_id = session_user_id(conn, token)
            if not user_id:
                return expired()
            if request.method == "DELETE":
                conn.execute("DELETE FROM sessions WHERE token_hash=%s", (token_hash(token),))
                response = jsonify(loggedOut=True)
                response.delete_cookie(COOKIE)
                return response
            user = conn.execute("SELECT id, username, role FROM users WHERE id=%s", (user_id,)).fetchone()
            return jsonify(user=dict(id=user["id"], login=user["username"],
                                     displayName=user["username"],
                                     role="operator" if user["role"]=="operator" else "trainee"),
                           aiMode=mode, demoOperator=app.config["DEMO_OPERATOR"])

    @app.post("/api/events")
    def task_returned():
        token = request.cookies.get(COOKIE)
        if not token:
            return expired()
        with connect() as conn:
            user_id = session_user_id(conn, token)
            if not user_id:
                return expired()
            payload = request.get_json(silent=True)
            if (not isinstance(payload, dict) or set(payload) != {"name", "taskId", "requestId"}
                    or payload["name"] != "task_link_opened"):
                return jsonify(code="invalid_input", message="Проверьте ввод"), 400
            state = read_workspace(conn, user_id, lock=True)
            if (not state["task"] or state["task"]["taskId"] != payload["taskId"]
                    or state["effectiveAccess"] != "granted"
                    or payload["requestId"] != (state["request"]["requestId"] if state["request"] else None)):
                return jsonify(code="forbidden", message="Операция недоступна"), 403
            conn.execute("""
                INSERT INTO onboarding_events(assignment_id,name)
                VALUES (%s,'task_link_opened') ON CONFLICT DO NOTHING
            """, (state["task"]["taskId"],))
            return jsonify(recorded=True)

    @app.get("/api/workspace")
    def workspace():
        token = request.cookies.get(COOKIE)
        if not token:
            return expired()
        with connect() as conn:
            user_id = session_user_id(conn, token)
            if not user_id:
                return expired()
            return jsonify(read_workspace(conn, user_id))

    @app.post("/api/messages")
    def message():
        token = request.cookies.get(COOKIE)
        if not token:
            return expired()
        with connect() as conn:
            user_id = session_user_id(conn, token)
            if not user_id:
                return expired()
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or set(data) != {"text"}:
                return jsonify(code="invalid_input", message="Проверьте ввод"), 400
            text = data["text"]
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                return jsonify(code="invalid_input", message="Проверьте ввод"), 400
            snapshot = read_workspace(conn, user_id)

        # Release the DB connection before the external call. Recheck visibility
        # before disclosing its answer or preparing a proposal.
        try:
            decision = runner.respond(text, snapshot)
        except AgentUnavailable:
            return unavailable(None)

        with connect() as conn:
            if session_user_id(conn, token) != user_id:
                return expired()
            state = read_workspace(conn, user_id, lock=True)
            if state != snapshot:
                return jsonify(code="conflict", message="Обновите состояние"), 409
            proposal = None
            if decision["kind"] == "propose_access":
                if state["request"] or state["effectiveAccess"] != "missing":
                    return jsonify(code="conflict", message="Обновите состояние"), 409
                proposal = create_proposal(conn, user_id)
                conn.execute("""
                    INSERT INTO onboarding_events(assignment_id, name)
                    VALUES (%s, 'blocker_reported') ON CONFLICT DO NOTHING
                """, (state["task"]["taskId"],))
            return jsonify(text=decision["text"], aiMode=mode, workspace=state,
                           source=state["source"] if decision["sourceId"] else None,
                           proposal=proposal)

    @app.post("/api/proposals/<proposal_id>/confirm")
    def confirm(proposal_id):
        token = request.cookies.get(COOKIE)
        if not token:
            return expired()
        with connect() as conn:
            user_id = session_user_id(conn, token)
            if not user_id:
                return expired()
            key = request.headers.get("Idempotency-Key", "")
            if "\x00" in proposal_id or request.stream.read(1):
                return jsonify(code="invalid_input", message="Проверьте ввод"), 400
            ticket = confirm_proposal(conn, user_id, proposal_id, key)
            state = read_workspace(conn, user_id, request_id=ticket["requestId"])
            if state["request"] is None:
                # The ticket's immutable scope must still be visible.
                raise AccessError(403, "Операция недоступна")
            return jsonify(state)

    app.register_blueprint(buddy_blueprint(connect, session_user_id, COOKIE, mode))
    if app.config["DEMO_OPERATOR"]:
        app.register_blueprint(operator_blueprint(connect, session_user_id, COOKIE))
    return app
