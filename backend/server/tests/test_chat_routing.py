"""Short conversational turns are routed before the knowledge-base fallback."""
from ai.buddy_intents import classify
from server.portal_chat import (
    _CORRECTION_RE,
    _GREETING_RE,
    _IDENTITY_RE,
    _TASK_HELP_RE,
    _WELLBEING_MARKERS,
)


def test_greeting_and_identity_questions_are_smalltalk():
    assert _GREETING_RE.match("Привет")
    assert _IDENTITY_RE.match("Привет ты кто?")
    assert _IDENTITY_RE.match("Кто ты такой?")


def test_user_correction_does_not_become_a_kb_search():
    assert _CORRECTION_RE.search("Это не онбординг")
    assert _CORRECTION_RE.search("Ты не понял, ответ не по теме")


def test_open_task_help_requests_clarification_not_a_random_definition():
    assert _TASK_HELP_RE.search("Как решить задачу?")
    assert classify("Как решить задачу?") == "feedback"


def test_work_fatigue_routes_to_human_support():
    assert classify("Я устал работать") == "mentor"
    assert any(marker in "я устал работать" for marker in _WELLBEING_MARKERS)
