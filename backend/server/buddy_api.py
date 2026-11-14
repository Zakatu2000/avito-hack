"""Buddy onboarding API: profile, full checklist, structured chat, typed actions,
competency assessment. Mounted at /api/buddy; the legacy /api contract stays
untouched (S01-S12 invariants preserved).
"""
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import BoundedSemaphore

from flask import Blueprint, jsonify, request

from server import actions, knowledge, onboarding, orchestrator

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GEMINI_PACK = FIXTURES / "gemini_report"

_ID = re.compile(r"^[a-z0-9-]{1,64}$")


def _unavailable(message="Помощник временно недоступен. Попробуйте позже."):
    return jsonify(code="unavailable", message=message), 503


def buddy_blueprint(connect, session_user_id, cookie_name, ai_mode, llm=None,
                    llm_slots=None, llm_wait=8.0):
    bp = Blueprint("buddy", __name__, url_prefix="/api/buddy")
    # Concurrency limit for outbound LLM calls: a slow provider must not pile
    # up worker threads; excess requests get an honest 503 instead of a queue.
    llm_slots = llm_slots if llm_slots is not None else BoundedSemaphore(4)

    def current_user(conn):
        token = request.cookies.get(cookie_name, "")
        if not token:
            return None
        return session_user_id(conn, token)

    def require_user(conn):
        user_id = current_user(conn)
        if user_id is None:
            return None, (jsonify(code="session_expired", message="Войдите снова"), 401)
        profile = onboarding.read_profile(conn.cursor(), user_id)
        if profile is None:
            return None, (jsonify(code="forbidden",
                                  message="Для этого аккаунта нет профиля онбординга"), 403)
        return (user_id, profile), None

    def bad_input(message="Проверьте ввод"):
        return jsonify(code="invalid_input", message=message), 400

    @bp.get("/bootstrap")
    def bootstrap():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            cur = conn.cursor()
            decorated, progress = onboarding.read_checklist(cur, user_id, profile)
            next_items = onboarding.next_steps(cur, user_id, profile)
            manifest = json.loads((GEMINI_PACK / "images" / "manifest.json")
                                  .read_text(encoding="utf-8"))
            return jsonify(
                profile=onboarding.profile_card(profile),
                progress=progress,
                nextSteps=[{"id": d["id"], "title": d["title"], "status": d["status"],
                            "timing": d["timing"], "stageLabel": d["stageLabel"],
                            "stage": d["stage"], "actor": d["actor"]}
                           for d in next_items],
                checklistCount=len(decorated),
                aiMode=ai_mode,
                demoIntegrations="mock",
                geminiImages=[{"file": i["file"], "sha256": i["sha256"],
                               "altText": i["altText"]} for i in manifest["images"]],
            )

    @bp.get("/checklist")
    def checklist():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            cur = conn.cursor()
            decorated, progress = onboarding.read_checklist(cur, user_id, profile)
            return jsonify(items=decorated, progress=progress,
                           profile=onboarding.profile_card(profile))

    @bp.post("/checklist/<item_id>/transition")
    def transition(item_id):
        if not _ID.match(item_id):
            return bad_input()
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            data = request.get_json(silent=True)
            if (not isinstance(data, dict)
                    or not set(data) <= {"target", "evidenceUri", "note"}
                    or data.get("target") not in ("available", "in_progress",
                                                  "evidence_pending", "completed",
                                                  "blocked")):
                return bad_input()
            evidence = data.get("evidenceUri")
            note = data.get("note", "")
            if evidence is not None and (not isinstance(evidence, str)
                                         or len(evidence) > 500):
                return bad_input()
            if not isinstance(note, str) or len(note) > 1000:
                return bad_input()
            decorated, error = onboarding.transition(
                conn.cursor(), user_id, profile, item_id, data["target"],
                evidence_uri=evidence, note=note)
            if error:
                code, message = error
                status = {"not_found": 403, "forbidden": 403,
                          "conflict": 409}[code]
                return jsonify(code=code, message=message), status
            actions._audit(conn.cursor(), user_id, None, "checklist_transition",
                           {"itemId": item_id, "target": data["target"]})
            _, progress = onboarding.read_checklist(conn.cursor(), user_id, profile)
            return jsonify(item=decorated, progress=progress)

    @bp.post("/chat")
    def chat():
        # Input validation needs no DB; fail fast before touching the pool.
        data = request.get_json(silent=True)
        if (not isinstance(data, dict) or set(data) != {"text"}
                or not isinstance(data["text"], str)
                or not data["text"].strip() or len(data["text"]) > 4000):
            return bad_input()
        text = data["text"].strip()

        # Phase 1 (short transaction): facts, deterministic routing, writes.
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            payload, llm_request = orchestrator.prepare(
                conn.cursor(), user_id, profile, text, ai_mode,
                want_llm=llm is not None)
            if llm_request is None:
                conn.execute(
                    "INSERT INTO conversation_memory (user_id, summary) "
                    "VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE "
                    "SET summary = EXCLUDED.summary, updated_at = now()",
                    (user_id, f"last_intent={payload['intent']}"))

        # Phase 2 (NO DB connection held): the provider call, bounded by a
        # concurrency limit so a slow provider cannot pile up workers.
        if llm_request is not None:
            if not llm_slots.acquire(timeout=llm_wait):
                return _unavailable("Помощник перегружен. "
                                    "Попробуйте через минуту.")
            try:
                response = orchestrator.call_provider(llm, llm_request)
            except orchestrator.BuddyProviderUnavailable:
                # Live provider failed: honest 503, never a demo answer under
                # a live aiMode.
                return _unavailable()
            finally:
                llm_slots.release()
            # Phase 3 (fresh short transaction): guarded LLM text / steered
            # read-only re-route, only if the user session and fact snapshot
            # are still current; then persist conversation memory.
            with connect() as conn:
                ctx, err = require_user(conn)
                if err:
                    return err
                current_user_id, current_profile = ctx
                if current_user_id != user_id:
                    return jsonify(code="session_expired",
                                   message="Войдите снова"), 401
                current_payload, current_request = orchestrator.prepare(
                    conn.cursor(), user_id, current_profile, text, ai_mode,
                    want_llm=True)
                if (current_request is None
                        or current_request.facts != llm_request.facts):
                    return jsonify(code="conflict",
                                   message="Состояние изменилось. Повторите запрос."), 409
                payload = orchestrator.finalize(
                    conn.cursor(), user_id, text, current_payload,
                    response, ai_mode)
                conn.execute(
                    "INSERT INTO conversation_memory (user_id, summary) "
                    "VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE "
                    "SET summary = EXCLUDED.summary, updated_at = now()",
                    (user_id, f"last_intent={payload['intent']}"))
        payload["aiMode"] = ai_mode
        return jsonify(payload)

    @bp.post("/actions/preview")
    def preview():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            data = request.get_json(silent=True)
            if (not isinstance(data, dict)
                    or not set(data) <= {"actionType", "payload", "checklistItemId"}
                    or not isinstance(data.get("actionType"), str)
                    or "payload" not in data):
                return bad_input()
            item_id = data.get("checklistItemId")
            if item_id is not None and not _ID.match(str(item_id)):
                return bad_input()
            try:
                preview_obj, duplicate = actions.create_preview(
                    conn.cursor(), user_id, data["actionType"], data["payload"],
                    checklist_item_id=item_id)
            except actions.ActionError as exc:
                return jsonify(code=exc.code, message=str(exc)), exc.status_code
            return jsonify(actionPreview=preview_obj, duplicatePreview=duplicate)

    @bp.post("/actions/<action_id>/confirm")
    def confirm(action_id):
        if not _ID.match(action_id):
            return bad_input()
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            data = request.get_json(silent=True) or {}
            token = data.get("confirmationToken")
            if not isinstance(token, str) or not token:
                return bad_input()
            client_key = request.headers.get("Idempotency-Key")
            try:
                result = actions.confirm_action(
                    conn.cursor(), user_id, action_id, token, client_key)
            except actions.ActionError as exc:
                return jsonify(code=exc.code, message=str(exc)), exc.status_code
            return jsonify(result)

    @bp.post("/actions/<action_id>/cancel")
    def cancel(action_id):
        if not _ID.match(action_id):
            return bad_input()
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            try:
                return jsonify(actions.cancel_action(
                    conn.cursor(), user_id, action_id))
            except actions.ActionError as exc:
                return jsonify(code=exc.code, message=str(exc)), exc.status_code

    @bp.get("/actions")
    def history():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            return jsonify(actions=actions.list_actions(conn.cursor(), user_id))

    @bp.get("/audit")
    def audit():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            return jsonify(events=actions.audit_log(conn.cursor(), user_id))

    # ---- competency assessment («Колесо компетенций») ----

    def _axes(track):
        fixture = json.loads((FIXTURES / "competency_axes.json")
                             .read_text(encoding="utf-8"))
        return fixture["tracks"][track], fixture

    @bp.get("/competency/axes")
    def axes():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            track_axes, fixture = _axes(profile["track"])
            return jsonify(axes=track_axes, scale=fixture["scale"],
                           source=fixture["source"])

    @bp.get("/competency/latest")
    def latest():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            row = conn.execute(
                "SELECT id, track, ratings, priorities, plan, evidence, created_at "
                "FROM competency_assessments WHERE user_id = %s "
                "ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
            if row is None:
                return jsonify(assessment=None)
            return jsonify(assessment={
                "id": row["id"], "track": row["track"],
                "ratings": row["ratings"], "priorities": row["priorities"],
                "plan": row["plan"], "evidence": row["evidence"],
                "createdAt": row["created_at"].isoformat()})

    @bp.post("/competency")
    def save_assessment():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return bad_input()
            ratings, priorities, plan = (data.get("ratings"), data.get("priorities"),
                                         data.get("plan"))
            evidence = data.get("evidence") or {}
            track_axes, fixture = _axes(profile["track"])
            axis_ids = {a["id"] for a in track_axes}
            if (not isinstance(ratings, dict) or set(ratings) != axis_ids
                    or not all(isinstance(v, int) and 0 <= v <= 10
                               for v in ratings.values())):
                return bad_input("Оценки нужны по всем 8 осям, целые 0–10")
            if (not isinstance(priorities, list)
                    or not 1 <= len(priorities) <= 2
                    or not set(priorities) <= axis_ids):
                return bad_input("Выберите 1–2 зоны развития из осей")
            stages = {code for _, code in onboarding.STAGE_BY_WEEK} | {"after-month-3"}
            if (not isinstance(plan, list) or not plan
                    or not all(isinstance(p, dict) and set(p) >= {"axisId", "action", "dueStage"}
                               and p["axisId"] in priorities
                               and isinstance(p["action"], str) and p["action"].strip()
                               and p["dueStage"] in stages for p in plan)):
                return bad_input("План: действия по выбранным осям со сроком")
            if not isinstance(evidence, dict):
                return bad_input()
            assessment_id = "wheel-" + secrets.token_hex(6)
            conn.execute(
                "INSERT INTO competency_assessments "
                "(id, user_id, track, ratings, priorities, plan, evidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (assessment_id, user_id, profile["track"],
                 json.dumps(ratings), json.dumps(priorities),
                 json.dumps(plan, ensure_ascii=False),
                 json.dumps(evidence, ensure_ascii=False)))
            cur = conn.cursor()
            actions._audit(cur, user_id, None, "competency_saved",
                           {"assessmentId": assessment_id})
            # The wheel is evidence for the analytics track item when present.
            conn.execute(
                "INSERT INTO checklist_state (user_id, item_id, status, evidence_uri, note) "
                "SELECT %s, 'analytics-02', 'evidence_pending', %s, 'Колесо компетенций' "
                "WHERE EXISTS (SELECT 1 FROM checklist_items WHERE id = 'analytics-02' "
                "              AND track = %s) "
                "ON CONFLICT (user_id, item_id) DO UPDATE SET "
                "status = CASE WHEN checklist_state.status = 'completed' "
                "              THEN 'completed' ELSE 'evidence_pending' END, "
                "evidence_uri = EXCLUDED.evidence_uri, updated_at = now()",
                (user_id, f"assessment:{assessment_id}", profile["track"]))
            return jsonify(assessment={
                "id": assessment_id, "track": profile["track"],
                "ratings": ratings, "priorities": priorities, "plan": plan,
                "evidence": evidence,
                "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    @bp.post("/competency/<assessment_id>/send")
    def send_assessment(assessment_id):
        if not _ID.match(assessment_id):
            return bad_input()
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            row = conn.execute(
                "SELECT id, ratings, priorities, plan FROM competency_assessments "
                "WHERE id = %s AND user_id = %s", (assessment_id, user_id)).fetchone()
            if row is None:
                return jsonify(code="forbidden", message="Оценка не найдена"), 403
            axes, _ = _axes(profile["track"])
            label = {a["id"]: a["label"] for a in axes}
            lines = [f"Колесо компетенций ({profile['track']}), самооценка 0–10:"]
            lines += [f"- {label[k]}: {row['ratings'][k]}/10"
                      for k in sorted(row["ratings"], key=row['ratings'].get)]
            lines.append("Зоны развития: " + ", ".join(label[p] for p in row["priorities"]))
            lines += [f"* {label[p['axisId']]}: {p['action']} — {p['dueStage']}"
                      for p in row["plan"]]
            preview_obj, duplicate = actions.create_preview(
                conn.cursor(), user_id, "development_plan",
                {"to": "curator", "subject": "План развития по колесу компетенций",
                 "body": "\n".join(lines), "assessmentId": assessment_id},
                checklist_item_id="analytics-02"
                if profile["track"] == "analytics" else None)
            return jsonify(actionPreview=preview_obj, duplicatePreview=duplicate)

    @bp.get("/curator/history")
    def curator_history():
        with connect() as conn:
            ctx, err = require_user(conn)
            if err:
                return err
            user_id, profile = ctx
            rows = conn.execute(
                "SELECT id, direction, channel, body, parsed, created_at "
                "FROM curator_messages WHERE user_id = %s ORDER BY id DESC LIMIT 20",
                (user_id,)).fetchall()
            return jsonify(messages=[{
                "id": r["id"], "direction": r["direction"], "channel": r["channel"],
                "body": r["body"], "parsed": r["parsed"],
                "at": r["created_at"].isoformat()} for r in rows])

    @bp.get("/gemini/images/<name>")
    def gemini_image(name):
        if not re.fullmatch(r"image[679]\.png", name or ""):
            return bad_input()
        from flask import send_file
        return send_file(GEMINI_PACK / "images" / name)

    return bp
