"""Knowledge search input is converted to valid, bounded PostgreSQL FTS syntax."""
from ai.buddy_intents import classify
from server.knowledge import _ts_query, find_by_topics, search
from server.portal_api import _query_summary


def test_ts_query_strips_operators_urls_and_punctuation():
    query = _ts_query("Не могу скачать файл: https://intranet.local/a?x=1 OR !unsafe")

    assert query == "не | могу | скачать | файл | https | intranet | local | or | unsafe"
    assert all(char not in query for char in ":/?=!")


def test_ts_query_deduplicates_and_caps_terms():
    query = _ts_query("ошибка ошибка сбой доступ Jira файл запрос наставник проект план документ")

    assert query == "ошибка | сбой | доступ | jira | файл | запрос | наставник | проект | план | документ"
    assert len(query.split(" | ")) <= 12


def test_search_passes_only_sanitized_tsquery():
    class Cursor:
        params = None
        sql = None

        def execute(self, sql, params):
            self.sql = sql
            self.params = params
            return self

        def fetchall(self):
            return []

    cursor = Cursor()
    result = search(cursor, "ошибка: [to_tsquery] ! (' OR true --)")

    assert result == []
    assert "d.source_status <> 'unavailable'" in cursor.sql
    assert cursor.params[0] == "ошибка | to | tsquery | or | true"


def test_topic_lookup_excludes_unavailable_sources():
    class Cursor:
        sql = ""

        def execute(self, sql, _params):
            self.sql = sql
            return self

        def fetchall(self):
            return []

    cursor = Cursor()
    assert find_by_topics(cursor, ["onboarding"]) == []
    assert "d.source_status <> 'unavailable'" in cursor.sql


def test_download_failures_route_to_troubleshooting_and_secrets_are_blocked():
    assert classify("Не могу скачать файл из системы") == "troubleshoot"
    assert classify("Можно начать другую задачу, если эта не завершена?") == "next_step"
    assert classify("Мой токен: Bearer abcdefghijklmnopqrstuvwxyz123456") == "unsafe"
    assert classify("API key=sk-abcdefghijklmnopqrstuvwxyz123456") == "unsafe"


def test_abstention_summary_masks_contact_details_and_is_bounded():
    summary = _query_summary("Позвоните мне +7 (999) 123-45-67 или напишите a.person@example.test")

    assert "+7" not in summary
    assert "a.person@example.test" not in summary
    assert "[номер скрыт]" in summary
    assert "[email скрыт]" in summary
    assert len(_query_summary("тема " * 100)) <= 100
