"""Transactional migrations and synthetic fixtures for the First PR demo."""
import argparse
import hashlib
import os
import re
from pathlib import Path

import psycopg
from psycopg.rows import tuple_row
from werkzeug.security import generate_password_hash

MIGRATIONS = Path(__file__).parent / "migrations"
FIXTURE_VERSION = "b2-v1"
ACCOUNTS = (
    ("intern-01", "intern-demo", "intern", "team-alpha"),
    ("intern-02", "intern-ready", "intern", "team-beta"),
    ("intern-03", "intern-new", "intern", "team-alpha"),
    ("operator-01", "operator-demo", "operator", "team-alpha"),
)
# Serialize migration/seed/reset even if two processes start the demo together.
STORE_LOCK = 802604023


def migrate(conn):
    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (STORE_LOCK,))
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name text PRIMARY KEY, checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        cur.execute("SELECT name, checksum FROM schema_migrations ORDER BY name")
        applied = dict(cur.fetchall())
        files = sorted(MIGRATIONS.glob("*.sql"))
        if list(applied) != [p.name for p in files[:len(applied)]]:
            raise ValueError("Migration history does not match local files.")
        for path in files:
            sql = path.read_bytes()
            checksum = hashlib.sha256(sql).hexdigest()
            if path.name in applied:
                if applied[path.name] != checksum:
                    raise ValueError(f"An applied migration was changed: {path.name}")
                continue
            cur.execute(sql.decode())
            cur.execute("INSERT INTO schema_migrations (name, checksum) VALUES (%s, %s)",
                        (path.name, checksum))


def _lock_demo(cur):
    cur.execute("SELECT current_database()")
    name, = cur.fetchone()
    if not (name == "avito_buddy_demo" or re.fullmatch(r"avito_buddy_test_[a-z0-9_]+", name)):
        raise ValueError("Fixtures require avito_buddy_demo or avito_buddy_test_<suffix>.")
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (STORE_LOCK,))


def _install_accounts(cur):
    for uid, username, role, team in ACCOUNTS:
        cur.execute("""
            INSERT INTO users (id, username, password_hash, role, team_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (uid, username, generate_password_hash("training-only", method="pbkdf2:sha256:600000"), role, team))
    cur.executemany("""
        INSERT INTO assignments (id, user_id, resource_id, source_id, title)
        VALUES (%s, %s, %s, %s, %s)
    """, [
        ("task-01", "intern-01", "repo-intro", "demo-guide",
         "Открыть README учебного репозитория"),
        ("task-02", "intern-02", "repo-private", "demo-private-guide",
         "Открыть README закрытого учебного репозитория"),
    ])
    cur.execute("INSERT INTO access_grants VALUES ('intern-02', 'repo-private')")
    cur.execute("""
        INSERT INTO access_requests (id, assignment_id, status)
        VALUES ('req-02', 'task-02', 'approved')
    """)


def seed(conn):
    """Install once. Re-running seed preserves all runtime state."""
    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cur:
        _lock_demo(cur)
        cur.execute("SELECT 1 FROM demo_seeds WHERE version = %s", (FIXTURE_VERSION,))
        if cur.fetchone():
            return
        # Fail on collisions; never adopt pre-existing objects as demo fixtures.
        cur.execute("INSERT INTO teams VALUES ('team-alpha'), ('team-beta')")
        cur.execute("""
            INSERT INTO resources VALUES ('repo-intro', 'team-alpha'),
                                         ('repo-private', 'team-beta')
        """)
        cur.executemany("INSERT INTO instructions (id, team_id, excerpt) VALUES (%s, %s, %s)", [
            ("demo-guide", "team-alpha",
             "Учебная инструкция. Подтвердите заявку на доступ к назначенному репозиторию."),
            ("demo-private-guide", "team-beta",
             "Учебная инструкция закрытой команды. Начните с README."),
        ])
        _install_accounts(cur)
        cur.execute("INSERT INTO demo_seeds (version) VALUES (%s)", (FIXTURE_VERSION,))


def reset_demo(conn):
    """Rebuild only the four synthetic identities and their dependent state."""
    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cur:
        _lock_demo(cur)
        cur.execute("SELECT 1 FROM demo_seeds WHERE version = %s", (FIXTURE_VERSION,))
        if not cur.fetchone():
            raise ValueError("No installed demo fixtures to reset. Run seed first.")
        cur.execute("DELETE FROM users WHERE id = ANY(%s)", ([a[0] for a in ACCOUNTS],))
        _install_accounts(cur)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    commands.add_parser("seed")
    reset = commands.add_parser("reset-demo")
    reset.add_argument("--confirm", required=True, action="store_true",
                       help="Rebuild demo accounts and invalidate their sessions")
    args = parser.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        parser.error("Set DATABASE_URL.")
    with psycopg.connect(dsn) as conn:
        actions = {"migrate": migrate, "seed": seed, "reset-demo": reset_demo}
        actions[args.command](conn)
    print(f"{args.command}: OK")


if __name__ == "__main__":
    main()
