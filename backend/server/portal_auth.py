"""Password authentication for the preserved frontend; no identity headers trusted."""
import hashlib
import hmac
import re
import secrets
from datetime import date

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

COOKIE = "buddy_session"
SESSION_SECONDS = 8 * 60 * 60
DUMMY_HASH = generate_password_hash("not-a-user-password")


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token):
    return hashlib.sha256(("csrf:" + token).encode()).hexdigest()


def public_user(row):
    return dict(id=row["user_id"], name=row["name"], role=row["role"],
                roleLabel={"intern": "Стажёр", "mentor": "Наставник", "lead": "Руководитель"}[row["role"]],
                team=row["team"], initials="".join(p[0] for p in row["name"].split()[:2]).upper())


def current_account(conn):
    return conn.execute(
        "SELECT a.* FROM portal_accounts a JOIN sessions s ON s.user_id=a.user_id "
        "WHERE s.token_hash=%s AND s.expires_at>now()",
        (token_hash(request.cookies.get(COOKIE, "")),)).fetchone()


def create_account(conn, email, password, name, role="intern", track="backend"):
    """Used by registration and the interactive provisioning CLI (no default passwords)."""
    if role not in ("intern", "mentor", "lead") or track not in ("backend", "analytics", "marketing"):
        raise ValueError("Invalid role or track")
    user_id = "portal-" + secrets.token_hex(12)
    conn.execute("INSERT INTO teams(id) VALUES ('portal-team') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO users(id,username,password_hash,role,team_id) VALUES (%s,%s,%s,'intern','portal-team')",
                 (user_id, email, generate_password_hash(password)))
    conn.execute("INSERT INTO portal_accounts(user_id,email,name,role) VALUES (%s,%s,%s,%s)",
                 (user_id, email, name, role))
    conn.execute("INSERT INTO intern_profiles(user_id,track,role_code,grade,week_no,start_date,mentor_name,curator_name,unit) "
                 "VALUES (%s,%s,'PORTAL_INTERN','INT',1,%s,'Наставник','Куратор','Platform Interns')",
                 (user_id, track, date.today()))
    return conn.execute("SELECT * FROM portal_accounts WHERE user_id=%s", (user_id,)).fetchone()


def valid_credentials(data, registration=False):
    expected = {"email", "password", "name"} if registration else {"email", "password"}
    if not isinstance(data, dict) or set(data) != expected:
        return False
    if not all(isinstance(v, str) and "\x00" not in v for v in data.values()):
        return False
    if not re.fullmatch(r"[^\s@]{1,64}@[^\s@]{1,189}\.[^\s@]{2,63}", data["email"]) or len(data["email"]) > 254:
        return False
    if not 1 <= len(data["password"]) <= 128:
        return False
    return not registration or (12 <= len(data["password"]) and 2 <= len(data["name"].strip()) <= 100)


def auth_blueprint(connect):
    bp = Blueprint("portal_auth", __name__)

    @bp.before_app_request
    def protect_portal():
        if not request.path.startswith("/api/"):
            return None
        # Original API remains available for its regression tests / standalone use.
        # Integrated deployment also protects its mutating routes with the portal CSRF token.
        endpoint = request.endpoint or ""
        portal = endpoint.startswith(("portal.", "portal_auth."))
        integrated = current_app.config.get("PORTAL_PROTECT_LEGACY", False)
        if not portal and not integrated:
            return None
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("Origin")
            allowed = current_app.config.get("PUBLIC_ORIGIN") or request.host_url.rstrip("/")
            if origin and origin.rstrip("/") != allowed:
                return jsonify(code="FORBIDDEN", message="Недопустимый источник запроса"), 403
            if endpoint not in ("portal_auth.login", "portal_auth.register", "login"):
                token = request.cookies.get(COOKIE, "")
                supplied = request.headers.get("X-CSRF-Token", "")
                if not token or not hmac.compare_digest(supplied, csrf_token(token)):
                    return jsonify(code="FORBIDDEN", message="Обновите страницу и повторите запрос"), 403

    def limited(email):
        # Both per-account and per-IP buckets. Commit independently of failed login.
        buckets = ("email:" + email, "ip:" + (request.remote_addr or "unknown"))
        with connect() as conn:
            conn.execute("DELETE FROM portal_auth_limits WHERE expires_at < now()")
            for value in buckets:
                row = conn.execute(
                    "INSERT INTO portal_auth_limits(bucket,attempts,expires_at) VALUES (%s,1,now()+interval '15 minutes') "
                    "ON CONFLICT(bucket) DO UPDATE SET attempts=portal_auth_limits.attempts+1 RETURNING attempts",
                    (token_hash(value),)).fetchone()
                if row["attempts"] > (10 if value.startswith("email:") else 100):
                    return True
        return False

    def establish(conn, account):
        previous = request.cookies.get(COOKIE)
        if previous:
            conn.execute("DELETE FROM sessions WHERE token_hash=%s", (token_hash(previous),))
        conn.execute("DELETE FROM sessions WHERE expires_at <= now()")
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+make_interval(secs=>%s))",
                     (token_hash(token), account["user_id"], SESSION_SECONDS))
        response = jsonify(user=public_user(account), csrfToken=csrf_token(token))
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
                            samesite="Strict", path="/")
        return response

    @bp.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True)
        if not valid_credentials(data, True):
            return jsonify(code="BAD_REQUEST", message="Укажите имя, email и пароль от 12 до 128 символов"), 400
        email = data["email"].strip().lower()
        if limited(email):
            return jsonify(code="RATE_LIMITED", message="Слишком много попыток. Повторите через 15 минут"), 429
        import psycopg
        try:
            with connect() as conn:
                account = create_account(conn, email, data["password"], data["name"].strip())
                response = establish(conn, account)
                response.status_code = 201
                return response
        except psycopg.errors.UniqueViolation:
            return jsonify(code="CONFLICT", message="Не удалось создать аккаунт с этим email"), 409

    @bp.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True)
        if not valid_credentials(data):
            return jsonify(code="BAD_REQUEST", message="Укажите корректные email и пароль"), 400
        email = data["email"].strip().lower()
        if limited(email):
            return jsonify(code="RATE_LIMITED", message="Слишком много попыток. Повторите через 15 минут"), 429
        with connect() as conn:
            row = conn.execute("SELECT a.*,u.password_hash FROM portal_accounts a JOIN users u ON u.id=a.user_id WHERE a.email=%s",
                               (email,)).fetchone()
            valid = check_password_hash(row["password_hash"] if row else DUMMY_HASH, data["password"])
            if not row or not valid:
                return jsonify(code="UNAUTHENTICATED", message="Неверный email или пароль"), 401
            return establish(conn, row)

    @bp.get("/api/auth/session")
    def session():
        with connect() as conn:
            account = current_account(conn)
            if not account:
                return jsonify(code="UNAUTHENTICATED", message="Войдите в аккаунт"), 401
            return jsonify(user=public_user(account), csrfToken=csrf_token(request.cookies[COOKIE]))

    @bp.post("/api/auth/logout")
    def logout():
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=%s", (token_hash(request.cookies.get(COOKIE, "")),))
        response = jsonify(loggedOut=True)
        response.delete_cookie(COOKIE, path="/", samesite="Strict",
                               secure=current_app.config.get("SESSION_COOKIE_SECURE", False), httponly=True)
        return response

    return bp
