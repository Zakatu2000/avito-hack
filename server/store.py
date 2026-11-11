"""Transactional migrations and synthetic fixtures for the First PR demo."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import psycopg
from psycopg.rows import tuple_row
from werkzeug.security import generate_password_hash

MIGRATIONS = Path(__file__).parent / "migrations"
FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_VERSION = "b2-v1"
ONBOARDING_FIXTURE_VERSION = "onboarding-v1"
ACCOUNTS = (
    ("intern-01", "intern-demo", "intern", "team-alpha"),
    ("intern-02", "intern-ready", "intern", "team-beta"),
    ("intern-03", "intern-new", "intern", "team-alpha"),
    ("operator-01", "operator-demo", "operator", "team-alpha"),
    ("intern-04", "intern-analytics", "intern", "team-alpha"),
    ("intern-05", "intern-marketing", "intern", "team-alpha"),
)
# Onboarding demo profiles (track, role code, grade, week, mentor, curator, unit).
ONBOARDING_PROFILES = {
    "intern-01": ("backend", "ROLE_BACKEND_E1", "E1", 1,
                  "Илья С. (наставник)", "Мария К. (куратор)", "Юнит «Товары»"),
    "intern-02": ("backend", "ROLE_BACKEND_E1", "E1", 2,
                  "Илья С. (наставник)", "Мария К. (куратор)", "Юнит «Товары»"),
    "intern-03": ("backend", "ROLE_BACKEND_E1", "E1", 1,
                  "Илья С. (наставник)", "Мария К. (куратор)", "Юнит «Товары»"),
    "intern-04": ("analytics", "ROLE_ANALYTICS_INT", "INT", 1,
                  "Ольга Р. (наставник)", "Мария К. (куратор)", "Аналитика юнита"),
    "intern-05": ("marketing", "ROLE_MARKETING_INT", "INT", 1,
                  "Павел Д. (бадди)", "Мария К. (куратор)", "Маркетинг спроса"),
}
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


def is_demo_database(name):
    return name == "avito_buddy_demo" or re.fullmatch(r"avito_buddy_test_[a-z0-9_]+", name) is not None


def _lock_demo(cur):
    cur.execute("SELECT current_database()")
    name, = cur.fetchone()
    if not is_demo_database(name):
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
            seed_onboarding(cur)
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
        seed_onboarding(cur)


def _load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def seed_onboarding(cur):
    """Idempotent onboarding fixtures: catalog/KB upserted, runtime state kept."""
    cur.execute("SELECT 1 FROM demo_seeds WHERE version = %s",
                (ONBOARDING_FIXTURE_VERSION,))
    installed = cur.fetchone() is not None

    # Accounts added after the original b2-v1 fixtures: create only if missing
    # (old demo DBs upgrade in place; fresh installs already have them).
    for uid, username, role, team in ACCOUNTS:
        if uid in ("intern-04", "intern-05"):
            cur.execute("""
                INSERT INTO users (id, username, password_hash, role, team_id)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
            """, (uid, username,
                  generate_password_hash("training-only", method="pbkdf2:sha256:600000"),
                  role, team))

    catalog = _load_fixture("checklist_catalog.json")
    for item in catalog["items"]:
        cur.execute("""
            INSERT INTO checklist_items
                (id, track, title, original_text, description, instructions,
                 stage, stage_order, stage_label, actor, prerequisites,
                 objective, evidence, completion_policy, source_ref)
            VALUES (%(id)s, %(track)s, %(title)s, %(originalText)s, %(description)s,
                    %(instructions)s, %(stage)s, %(stageOrder)s, %(stageLabel)s,
                    %(actor)s, %(prerequisites)s, %(objective)s, %(evidence)s,
                    %(completionPolicy)s, %(sourceRef)s)
            ON CONFLICT (id) DO UPDATE SET
                track = EXCLUDED.track, title = EXCLUDED.title,
                original_text = EXCLUDED.original_text,
                description = EXCLUDED.description,
                instructions = EXCLUDED.instructions,
                stage = EXCLUDED.stage, stage_order = EXCLUDED.stage_order,
                stage_label = EXCLUDED.stage_label, actor = EXCLUDED.actor,
                prerequisites = EXCLUDED.prerequisites,
                objective = EXCLUDED.objective, evidence = EXCLUDED.evidence,
                completion_policy = EXCLUDED.completion_policy,
                source_ref = EXCLUDED.source_ref
        """, {**item,
              "instructions": json.dumps(item["instructions"], ensure_ascii=False),
              "prerequisites": json.dumps(item["prerequisites"], ensure_ascii=False),
              "sourceRef": json.dumps(item["sourceRef"], ensure_ascii=False)})

    kb = _load_fixture("knowledge_base.json")
    for doc in kb["documents"]:
        cur.execute("""
            INSERT INTO kb_documents
                (id, title, source_type, url, version, freshness, tracks, roles,
                 governance, source_status)
            VALUES (%(id)s, %(title)s, %(sourceType)s, %(url)s, %(version)s,
                    %(freshness)s, %(tracks)s, %(roles)s, %(governance)s,
                    %(sourceStatus)s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title, source_type = EXCLUDED.source_type,
                url = EXCLUDED.url, version = EXCLUDED.version,
                freshness = EXCLUDED.freshness, tracks = EXCLUDED.tracks,
                roles = EXCLUDED.roles, governance = EXCLUDED.governance,
                source_status = EXCLUDED.source_status
        """, {**doc,
              "tracks": json.dumps(doc["tracks"], ensure_ascii=False),
              "roles": json.dumps(doc["roles"], ensure_ascii=False),
              "sourceStatus": doc.get("sourceStatus", "verified")})
        for chunk in doc["chunks"]:
            cur.execute("""
                INSERT INTO kb_chunks
                    (id, doc_id, title, body, quote, topics, conflict_note,
                     checklist_refs)
                VALUES (%(id)s, %(doc_id)s, %(title)s, %(body)s, %(quote)s,
                        %(topics)s, %(conflict_note)s, %(checklist_refs)s)
                ON CONFLICT (id) DO UPDATE SET
                    doc_id = EXCLUDED.doc_id, title = EXCLUDED.title,
                    body = EXCLUDED.body, quote = EXCLUDED.quote,
                    topics = EXCLUDED.topics,
                    conflict_note = EXCLUDED.conflict_note,
                    checklist_refs = EXCLUDED.checklist_refs
            """, {"id": chunk["id"], "doc_id": doc["id"], "title": chunk["title"],
                  "body": chunk["text"], "quote": chunk["quote"],
                  "topics": json.dumps(chunk["topics"], ensure_ascii=False),
                  "conflict_note": chunk.get("conflictNote"),
                  "checklist_refs": json.dumps(chunk.get("checklistRefs", []),
                                               ensure_ascii=False)})

    for user_id, (track, role, grade, week, mentor, curator, unit) in \
            ONBOARDING_PROFILES.items():
        cur.execute("""
            INSERT INTO intern_profiles
                (user_id, track, role_code, grade, week_no, mentor_name,
                 curator_name, unit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, track, role, grade, week, mentor, curator, unit))

    if not installed:
        # First install only: a starter state so judges see the lifecycle
        # variety without replaying weeks of work. Runtime edits survive re-seed.
        starter = [
            ("intern-01", "common-01", "in_progress", None,
             "Ждём подтверждения наставника по чатам и доступам"),
        ]
        for user_id, item_id, status, evidence, note in starter:
            cur.execute("""
                INSERT INTO checklist_state (user_id, item_id, status, evidence_uri, note)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id, item_id) DO NOTHING
            """, (user_id, item_id, status, evidence, note))
        cur.execute("INSERT INTO demo_seeds (version) VALUES (%s)",
                    (ONBOARDING_FIXTURE_VERSION,))


def reset_onboarding_runtime(cur):
    """Reset only runtime onboarding state of demo accounts (catalog/KB stay)."""
    user_ids = list(ONBOARDING_PROFILES)
    for table in ("checklist_state", "learning_records", "competency_assessments",
                  "curator_messages", "conversation_memory"):
        cur.execute(f"DELETE FROM {table} WHERE user_id = ANY(%s)", (user_ids,))
    cur.execute("DELETE FROM pending_actions WHERE user_id = ANY(%s)", (user_ids,))
    cur.execute("DELETE FROM action_audit WHERE user_id = ANY(%s)", (user_ids,))
    cur.execute("DELETE FROM demo_seeds WHERE version = %s",
                (ONBOARDING_FIXTURE_VERSION,))
    seed_onboarding(cur)


def reset_demo(conn):
    """Rebuild only the synthetic identities and their dependent state."""
    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cur:
        _lock_demo(cur)
        cur.execute("SELECT 1 FROM demo_seeds WHERE version = %s", (FIXTURE_VERSION,))
        if not cur.fetchone():
            raise ValueError("No installed demo fixtures to reset. Run seed first.")
        cur.execute("DELETE FROM users WHERE id = ANY(%s)", ([a[0] for a in ACCOUNTS],))
        _install_accounts(cur)
        reset_onboarding_runtime(cur)


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
