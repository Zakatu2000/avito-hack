"""Onboarding domain logic: profiles, checklist lifecycle, progress, next steps.

All state transitions live here on the server; the agent layer only reads
snapshots. Lifecycle per docs/sdd/onboarding.md:

    available -> in_progress -> evidence_pending -> completed
    any state -> blocked (explicit blocker or unmet prerequisite)

`approved` access != granted right stays with the legacy tables; this module
never touches assignments/requests/grants.
"""
import json
from datetime import date
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# An item the mentor/curator must act on is shown to the intern as waiting on
# the human; the intern can only nudge it, not complete it.
HUMAN_ACTORS = ("mentor", "curator")

STAGE_BY_WEEK = (
    (1, "week-1"),
    (2, "week-2"),
    (5, "month-1"),
    (9, "month-2"),
    (13, "month-3"),
)
STAGE_ORDER = {"week-1": 1, "week-2": 2, "month-1": 3, "month-2": 4,
               "month-3": 5, "after-month-3": 6}

STATUS_RANK = {"available": 0, "blocked": 0, "in_progress": 1,
               "evidence_pending": 2, "completed": 3}

ALLOWED_TRANSITIONS = {
    "available": {"in_progress", "blocked"},
    "blocked": {"available", "in_progress"},
    "in_progress": {"evidence_pending", "completed", "blocked"},
    "evidence_pending": {"completed", "in_progress", "blocked"},
    "completed": set(),
}


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def current_stage_code(week_no):
    stage = "after-month-3"
    for max_week, code in STAGE_BY_WEEK:
        if week_no <= max_week:
            return code
    return stage


def item_visibility(item, profile):
    """Common items are shown to every profile; track items only to their own."""
    return item["track"] in ("common", profile["track"])


def _state_map(cur, user_id):
    rows = cur.execute(
        "SELECT item_id, status, evidence_uri, note, updated_at, started_at, completed_at "
        "FROM checklist_state WHERE user_id = %s", (user_id,)).fetchall()
    return {r["item_id"]: r for r in rows}


def _prereq_blockers(item, states):
    return [p for p in item["prerequisites"]
            if states.get(p, {}).get("status") != "completed"]


def compute_progress(items, states, profile):
    visible = [i for i in items if item_visibility(i, profile)]
    done = [i for i in visible if states.get(i["id"], {}).get("status") == "completed"]
    pct = round(100.0 * len(done) / len(visible), 1) if visible else 0.0
    return {"total": len(visible), "completed": len(done), "pct": pct}


def decorate_item(item, state, states, profile):
    """Attach lifecycle status, availability and overdue flag to a catalog row."""
    status = state["status"] if state else "available"
    blockers = _prereq_blockers(item, states)
    if status in ("available", "blocked"):
        status = "blocked" if blockers else "available"
    current_order = STAGE_ORDER[current_stage_code(profile["week_no"])]
    if status == "completed":
        timing = "done"
    elif item["stage_order"] < current_order:
        timing = "overdue"
    elif item["stage_order"] == current_order:
        timing = "now"
    else:
        timing = "next"
    return {
        "id": item["id"],
        "track": item["track"],
        "title": item["title"],
        "description": item["description"],
        "instructions": item["instructions"],
        "stage": item["stage"],
        "stageLabel": item["stage_label"],
        "stageOrder": item["stage_order"],
        "actor": item["actor"],
        "status": status,
        "timing": timing,
        "blockedBy": blockers,
        "evidence": item["evidence"],
        "objective": item["objective"],
        "completionPolicy": item["completion_policy"],
        "evidenceUri": state["evidence_uri"] if state else None,
        "note": state["note"] if state else "",
        "sourceRef": item["source_ref"],
        "dependencies": item["prerequisites"], "requiredAccess": item["required_access"],
        "priority": item["priority"], "estimatedMinutes": item["estimated_minutes"],
        "startedAt": state["started_at"].isoformat() if state and state["started_at"] else None,
        "completedAt": state["completed_at"].isoformat() if state and state["completed_at"] else None,
    }


def read_checklist(cur, user_id, profile):
    items = cur.execute(
        "SELECT * FROM checklist_items WHERE track IN ('common', %s) "
        "ORDER BY stage_order, id", (profile["track"],)).fetchall()
    states = _state_map(cur, user_id)
    decorated = [decorate_item(i, states.get(i["id"]), states, profile) for i in items]
    return decorated, compute_progress(items, states, profile)


def next_steps(cur, user_id, profile, limit=3):
    """Rank: now-overdue first, then in-progress, then earliest available stage."""
    decorated, _ = read_checklist(cur, user_id, profile)
    open_items = [d for d in decorated if d["status"] != "completed"]

    def rank(d):
        status_rank = {"in_progress": 0, "evidence_pending": 1,
                       "available": 2, "blocked": 3}[d["status"]]
        timing_rank = {"overdue": 0, "now": 1, "next": 2, "done": 3}[d["timing"]]
        return (status_rank if d["status"] != "blocked" else 3,
                timing_rank, d["stageOrder"], d["id"])

    return sorted(open_items, key=rank)[:limit]


def read_profile(cur, user_id):
    return cur.execute(
        "SELECT user_id, track, role_code, grade, week_no, start_date, "
        "       mentor_name, curator_name, unit "
        "FROM intern_profiles WHERE user_id = %s", (user_id,)).fetchone()


def transition(cur, user_id, profile, item_id, target, *, evidence_uri=None, note=""):
    """Server-side state machine. Returns (decorated_item, error)."""
    item = cur.execute(
        "SELECT * FROM checklist_items WHERE id = %s AND track IN ('common', %s)",
        (item_id, profile["track"])).fetchone()
    if item is None:
        return None, ("not_found", "Пункт чек-листа не найден")
    # Portal users can also reach the legacy Buddy endpoint. Share the
    # portal lock and its blockers at the common transition boundary.
    account = cur.execute("SELECT user_id FROM portal_accounts WHERE user_id=%s FOR UPDATE", (user_id,)).fetchone()
    if account and target in ("in_progress", "evidence_pending", "completed"):
        if item["required_access"]:
            grants = cur.execute(
                "SELECT DISTINCT system FROM portal_grants WHERE user_id=%s AND expires_at>now()", (user_id,),
            ).fetchall()
            if not set(item["required_access"]) <= {row["system"] for row in grants}:
                return None, ("conflict", "Для пункта требуется действующий доступ")
        blocker = cur.execute(
            "SELECT 1 FROM portal_requests WHERE user_id=%s AND task_id=%s AND data->>'kind'='technical_support' "
            "AND status IN ('sent','in_progress','resolved')", (user_id, item_id),
        ).fetchone()
        if blocker:
            return None, ("conflict", "Техническое обращение ожидает закрытия")
    states = _state_map(cur, user_id)
    current = states.get(item_id, {}).get("status", "available")
    if current == "available" and _prereq_blockers(item, states):
        current = "blocked"
    if target not in ALLOWED_TRANSITIONS[current] | ({current} if current == "blocked" else set()):
        if not (current == "blocked" and target in ("available", "in_progress")
                and not _prereq_blockers(item, states)):
            return None, ("conflict", f"Переход {current} → {target} недопустим")
    if current == "blocked" and target in ("available", "in_progress"):
        blockers = _prereq_blockers(item, states)
        if blockers:
            return None, ("conflict", "Сначала закройте пререквизиты: " + ", ".join(blockers))
    if target == "completed":
        if item["actor"] in HUMAN_ACTORS:
            return None, ("forbidden", "Этот пункт выполняет наставник/куратор — отметьте, когда он подтвердит")
        policy = item["completion_policy"]
        if policy == "evidence_required" and not evidence_uri and not (
                states.get(item_id, {}) or {}).get("evidence_uri"):
            return None, ("conflict", "Нужно доказательство выполнения (evidence)")
        if policy == "curator_confirmed":
            ok = cur.execute(
                "SELECT 1 FROM learning_records WHERE user_id = %s AND item_id = %s "
                "AND kind = 'evidence' AND payload->>'by' = 'curator'",
                (user_id, item_id)).fetchone()
            if not ok:
                return None, ("conflict", "Пункт подтверждается куратором")
    cur.execute(
        "INSERT INTO checklist_state (user_id, item_id, status, evidence_uri, note, started_at, completed_at) "
        "VALUES (%s, %s, %s, %s, %s, CASE WHEN %s='in_progress' THEN now() END, "
        "CASE WHEN %s='completed' THEN now() END) "
        "ON CONFLICT (user_id, item_id) DO UPDATE "
        "SET status = EXCLUDED.status, "
        "    evidence_uri = COALESCE(EXCLUDED.evidence_uri, checklist_state.evidence_uri), "
        "    note = EXCLUDED.note, updated_at = now(), "
        "    started_at = COALESCE(checklist_state.started_at, EXCLUDED.started_at), "
        "    completed_at = COALESCE(checklist_state.completed_at, EXCLUDED.completed_at)",
        (user_id, item_id, target, evidence_uri, note, target, target))
    if target == "completed" and evidence_uri:
        cur.execute(
            "INSERT INTO learning_records (user_id, item_id, kind, payload) "
            "VALUES (%s, %s, 'evidence', %s)",
            (user_id, item_id, json.dumps({"uri": evidence_uri, "by": "intern"})))
    states = _state_map(cur, user_id)
    return decorate_item(item, states.get(item_id), states, profile), None


def profile_card(profile):
    return {
        "track": profile["track"],
        "roleCode": profile["role_code"],
        "grade": profile["grade"],
        "weekNo": profile["week_no"],
        "startDate": profile["start_date"].isoformat()
        if isinstance(profile["start_date"], date) else profile["start_date"],
        "mentorName": profile["mentor_name"],
        "curatorName": profile["curator_name"],
        "unit": profile["unit"],
        "stage": current_stage_code(profile["week_no"]),
    }
