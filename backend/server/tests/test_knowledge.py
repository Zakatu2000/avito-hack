"""Knowledge search input is converted to valid, bounded PostgreSQL FTS syntax."""
from ai.buddy_intents import classify
from server.knowledge import _ts_query, find_by_topics, search
from server.portal_chat import _query_summary


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
    assert cursor.params["query"] == "ошибка | to | tsquery | or | true"


def test_search_drops_low_rank_generic_word_matches():
    def row(chunk_id, rank):
        return {
            "id": chunk_id,
            "doc_id": "playbook",
            "title": "section",
            "body": "snippet",
            "quote": "quote",
            "topics": [],
            "conflict_note": None,
            "checklist_refs": [],
            "source_type": "reference",
            "url": None,
            "version": "v1",
            "freshness": None,
            "source_locator": None, "synthetic": False, "tracks": [],
            "difficulty": None, "estimated_minutes": None,
            "source_status": "verified",
            "doc_title": "Playbook",
            "rank": rank,
        }

    class Cursor:
        def execute(self, _sql, _params):
            self.min_rank = _params["min_rank"]
            return self

        def fetchall(self):
            return [row_ for row_ in [
                row("one-common-word", 0.04137),
                row("fatigue-keyword-only", 0.04449),
                row("strong-match", 0.06206),
                row("zero-bug-policy", 0.04965),
            ] if row_["rank"] >= self.min_rank]

    results = search(Cursor(), "задача работать", min_rank=0.045)

    assert [source["chunkId"] for source in results] == ["strong-match", "zero-bug-policy"]


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
