"""Onboarding domain: profiles, catalog visibility, lifecycle, progress."""
import pytest

from server import onboarding


def test_profiles_seeded_for_all_demo_interns(db):
    for uid, track in (("intern-01", "backend"), ("intern-02", "backend"),
                       ("intern-03", "backend"), ("intern-04", "analytics"),
                       ("intern-05", "marketing")):
        profile = onboarding.read_profile(db.cursor(), uid)
        assert profile is not None and profile["track"] == track


def test_backend_sees_common_and_backend_items_only(db):
    profile = onboarding.read_profile(db.cursor(), "intern-01")
    items, progress = onboarding.read_checklist(db.cursor(), "intern-01", profile)
    tracks = {i["track"] for i in items}
    assert tracks == {"common", "backend"}
    assert progress["total"] == 48  # 16 common + 32 backend rows of the XLSX
    assert progress["completed"] == 0


def test_analytics_sees_same_common_checklist_plus_own_track(db):
    profile = onboarding.read_profile(db.cursor(), "intern-04")
    items, _ = onboarding.read_checklist(db.cursor(), "intern-04", profile)
    tracks = {i["track"] for i in items}
    assert tracks == {"common", "analytics"}
    common = [i for i in items if i["track"] == "common"]
    assert len(common) == 16  # the whole common sheet for every profile


def test_marketing_sees_common_and_marketing(db):
    profile = onboarding.read_profile(db.cursor(), "intern-05")
    items, _ = onboarding.read_checklist(db.cursor(), "intern-05", profile)
    assert {i["track"] for i in items} == {"common", "marketing"}


def test_lifecycle_happy_path(db):
    profile = onboarding.read_profile(db.cursor(), "intern-01")
    item, err = onboarding.transition(db.cursor(), "intern-01", profile,
                                      "backend-09", "in_progress")
    assert err is None and item["status"] == "in_progress"
    item, err = onboarding.transition(db.cursor(), "intern-01", profile,
                                      "backend-09", "completed",
                                      evidence_uri="note://avito-cli")
    assert err is None and item["status"] == "completed"
    assert item["evidenceUri"] == "note://avito-cli"
    _, progress = onboarding.read_checklist(db.cursor(), "intern-01", profile)
    assert progress["completed"] == 1


def test_lifecycle_rejects_illegal_transitions(db):
    profile = onboarding.read_profile(db.cursor(), "intern-01")
    # available -> completed directly is not allowed
    _, err = onboarding.transition(db.cursor(), "intern-01", profile,
                                   "backend-10", "completed")
    assert err is not None and err[0] == "conflict"
    # completed is terminal
    onboarding.transition(db.cursor(), "intern-01", profile,
                          "backend-11", "in_progress")
    onboarding.transition(db.cursor(), "intern-01", profile,
                          "backend-11", "completed")
    _, err = onboarding.transition(db.cursor(), "intern-01", profile,
                                   "backend-11", "in_progress")
    assert err is not None and err[0] == "conflict"


def test_mentor_items_cannot_be_completed_by_intern(db):
    profile = onboarding.read_profile(db.cursor(), "intern-01")
    onboarding.transition(db.cursor(), "intern-01", profile,
                          "common-12", "in_progress")
    _, err = onboarding.transition(db.cursor(), "intern-01", profile,
                                   "common-12", "completed")
    assert err is not None and err[0] == "forbidden"


def test_foreign_track_item_is_not_found(db):
    profile = onboarding.read_profile(db.cursor(), "intern-04")  # analytics
    _, err = onboarding.transition(db.cursor(), "intern-04", profile,
                                   "backend-09", "in_progress")
    assert err is not None and err[0] == "not_found"


def test_next_steps_ranking(db):
    profile = onboarding.read_profile(db.cursor(), "intern-01")
    steps = onboarding.next_steps(db.cursor(), "intern-01", profile)
    assert steps and steps[0]["id"] == "common-01"  # starter in_progress
    assert all(s["status"] != "completed" for s in steps)


def test_blocked_item_unblocks_after_prereq(db):
    cur = db.cursor()
    cur.execute("UPDATE checklist_items SET prerequisites = '[\"backend-09\"]' "
                "WHERE id = 'backend-10'")
    profile = onboarding.read_profile(cur, "intern-01")
    _, err = onboarding.transition(cur, "intern-01", profile,
                                   "backend-10", "in_progress")
    assert err is not None and err[0] == "conflict"
    onboarding.transition(cur, "intern-01", profile, "backend-09", "in_progress")
    onboarding.transition(cur, "intern-01", profile, "backend-09", "completed")
    item, err = onboarding.transition(cur, "intern-01", profile,
                                      "backend-10", "in_progress")
    assert err is None and item["status"] == "in_progress"


def test_progress_counts_only_visible_items(db):
    profile = onboarding.read_profile(db.cursor(), "intern-01")
    onboarding.transition(db.cursor(), "intern-01", profile,
                          "common-02", "in_progress")
    onboarding.transition(db.cursor(), "intern-01", profile,
                          "common-02", "completed")
    _, progress = onboarding.read_checklist(db.cursor(), "intern-01", profile)
    assert progress == {"total": 48, "completed": 1, "pct": 2.1}
