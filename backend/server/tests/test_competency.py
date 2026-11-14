"""Competency assessment («Колесо компетенций») — full workflow without any
vision API: labels and ratings are entered manually; the DOCX images stay
attached as evidence via sha256 references (multimodal fallback)."""
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "server" / "fixtures"


def login(client, username="intern-demo"):
    reply = client.post("/api/session", json={"username": username,
                                              "password": "training-only"})
    assert reply.status_code == 200
    return reply


def _ratings(axes, value=6):
    return {a["id"]: value for a in axes}


def test_axes_schema_matches_gemini_pack(app):
    client = app.test_client()
    login(client)
    data = client.get("/api/buddy/competency/axes").get_json()
    assert len(data["axes"]) == 8  # exactly 8 axes per the Gemini exercise
    assert data["scale"] == {"min": 0, "max": 10}
    assert data["source"]["type"] == "gemini_report"
    # The seven playbook blocks plus the track axis.
    labels = {a["label"] for a in data["axes"]}
    assert {"Экспертность", "Инженерная культура", "Ответственность за результат",
            "Ориентация на бизнес", "Agile Mindset", "Коммуникация",
            "Развитие себя и других"} <= labels


def test_save_assessment_and_send_plan_via_hitl(app, db):
    client = app.test_client()
    login(client)
    axes = client.get("/api/buddy/competency/axes").get_json()["axes"]
    manifest = json.loads((FIXTURES / "gemini_report" / "images" / "manifest.json")
                          .read_text(encoding="utf-8"))
    ratings = _ratings(axes)
    ratings["communication"] = 4  # weakest axis becomes the priority
    payload = {
        "ratings": ratings,
        "priorities": ["communication"],
        "plan": [{"axisId": "communication",
                  "action": "Вести конспект 1:1 и готовить повестку заранее",
                  "dueStage": "month-1"}],
        "evidence": {"images": [i["sha256"] for i in manifest["images"][:2]]},
    }
    saved = client.post("/api/buddy/competency", json=payload)
    assert saved.status_code == 200, saved.get_json()
    assessment = saved.get_json()["assessment"]
    assert assessment["ratings"]["communication"] == 4

    latest = client.get("/api/buddy/competency/latest").get_json()["assessment"]
    assert latest["id"] == assessment["id"]
    assert latest["evidence"]["images"] == payload["evidence"]["images"]

    # Sending the plan is a typed action: preview first, never auto-sent.
    preview = client.post(
        f"/api/buddy/competency/{assessment['id']}/send", json={}
    ).get_json()["actionPreview"]
    assert preview["actionType"] == "development_plan"
    assert preview["status"] == "draft_preview"
    assert "Коммуникация: 4/10" in preview["payload"]["body"]
    assert "Зоны развития" in preview["payload"]["body"]

    outbox = db.execute("SELECT count(*) AS c FROM curator_messages "
                        "WHERE user_id='intern-01' AND direction='out'"
                        ).fetchone()["c"]
    assert outbox == 0  # nothing sent before the human confirms

    confirmed = client.post(
        f"/api/buddy/actions/{preview['actionId']}/confirm",
        json={"confirmationToken": preview["confirmationToken"]}).get_json()
    assert confirmed["status"] == "executed"
    outbox = db.execute("SELECT direction, body FROM curator_messages "
                        "WHERE user_id='intern-01' AND direction='out'"
                        ).fetchall()
    assert len(outbox) == 1 and "Колесо компетенций" in outbox[0]["body"]


def test_assessment_validation_errors(app):
    client = app.test_client()
    login(client)
    axes = client.get("/api/buddy/competency/axes").get_json()["axes"]
    ratings = _ratings(axes)

    bad = dict(ratings)
    del bad["communication"]  # not all 8 axes
    reply = client.post("/api/buddy/competency", json={
        "ratings": bad, "priorities": ["communication"],
        "plan": [{"axisId": "communication", "action": "x", "dueStage": "month-1"}]})
    assert reply.status_code == 400

    too_high = dict(ratings, communication=11)
    reply = client.post("/api/buddy/competency", json={
        "ratings": too_high, "priorities": ["communication"],
        "plan": [{"axisId": "communication", "action": "x", "dueStage": "month-1"}]})
    assert reply.status_code == 400

    reply = client.post("/api/buddy/competency", json={  # 3 priorities > 2
        "ratings": ratings,
        "priorities": ["communication", "expertise", "ownership"],
        "plan": [{"axisId": "communication", "action": "x", "dueStage": "month-1"}]})
    assert reply.status_code == 400

    reply = client.post("/api/buddy/competency", json={  # plan off the priorities
        "ratings": ratings, "priorities": ["communication"],
        "plan": [{"axisId": "expertise", "action": "x", "dueStage": "month-1"}]})
    assert reply.status_code == 400


def test_assessment_is_per_user(app):
    client = app.test_client()
    login(client)
    axes = client.get("/api/buddy/competency/axes").get_json()["axes"]
    client.post("/api/buddy/competency", json={
        "ratings": _ratings(axes), "priorities": ["expertise"],
        "plan": [{"axisId": "expertise", "action": "учить Go", "dueStage": "month-1"}]})

    other = app.test_client()
    login(other, "intern-marketing")
    assert other.get("/api/buddy/competency/latest"
                     ).get_json()["assessment"] is None
    # another user's assessment id is not addressable
    own = client.get("/api/buddy/competency/latest").get_json()["assessment"]
    reply = other.post(f"/api/buddy/competency/{own['id']}/send", json={})
    assert reply.status_code == 403


def test_gemini_pack_integrity():
    """Extracted text, both images and hashes stay verifiable offline."""
    import hashlib
    manifest = json.loads((FIXTURES / "gemini_report" / "images" / "manifest.json")
                          .read_text(encoding="utf-8"))
    assert (FIXTURES / "gemini_report" / "source.docx").exists()
    text = (FIXTURES / "gemini_report" / "extracted_text.txt").read_text(
        encoding="utf-8")
    assert "CHK-30" in text and "Колесо" in text or "компетенц" in text
    for image in manifest["images"]:
        data = (FIXTURES / "gemini_report" / "images" / image["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == image["sha256"]
        assert image["altText"]
