"""Versioned knowledge base retrieval: metadata filters + full-text search.

Hybrid = structured metadata (tier/track/role/topics) + Postgres FTS
(russian). Every hit carries its source citation; answers must cite chunks.
External providers never receive personal data: retrieval is fully local.
"""

import re

MIN_RELEVANCE_SCORE = 0.045

TIER_BY_SOURCE_TYPE = {
    "normative": "NORMATIVE",
    "reference": "PRIMARY_PLAYBOOK",
    "educational": "COURSE_SPEC",
    "public_context": "SECONDARY_PUBLIC",
}

def _ts_query(text):
    # to_tsquery accepts operators and syntax characters. Build its OR query
    # only from extracted word tokens so punctuation, URLs, and pasted logs
    # cannot produce a PostgreSQL syntax error or alter query semantics.
    terms = re.findall(r"[0-9a-zа-яё]{2,}", (text or "").casefold())
    terms = list(dict.fromkeys(terms))[:12]
    if not terms:
        return None
    return " | ".join(terms)


def search(cur, query, *, track=None, limit=4):
    """Return ranked chunks with citations. Deterministic, no LLM involved."""
    tsq = _ts_query(query)
    rows = cur.execute(
        """
        SELECT c.id, c.doc_id, c.title, c.body, c.quote, c.topics,
               c.conflict_note, c.checklist_refs,
               d.source_type, d.url, d.version, d.freshness, d.governance,
               d.source_status, d.title AS doc_title,
               CASE WHEN %s::text IS NULL THEN 0.0
                    ELSE ts_rank(c.fts, to_tsquery('russian', %s)) END AS rank
        FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id
        WHERE d.source_status <> 'unavailable'
          AND (d.tracks = '[]'::jsonb OR d.tracks ? 'common'
                OR (%s::text IS NOT NULL AND d.tracks ? %s))
          AND (%s::text IS NULL OR c.fts @@ to_tsquery('russian', %s))
        ORDER BY rank DESC, c.id
        LIMIT %s
        """,
        (tsq, tsq, track, track, tsq, tsq, limit * 3)).fetchall()
    citations = []
    for r in rows:
        citations.append({
            "chunkId": r["id"],
            "docId": r["doc_id"],
            "title": r["doc_title"],
            "section": r["title"],
            "url": r["url"],
            "tier": TIER_BY_SOURCE_TYPE[r["source_type"]],
            "sourceType": r["source_type"],
            "sourceStatus": r["source_status"],
            "freshness": r["freshness"],
            "quote": r["quote"],
            "conflictNote": r["conflict_note"],
            "snippet": r["body"][:400],
            "topics": r["topics"],
            "checklistRefs": r["checklist_refs"],
            "score": round(float(r["rank"]), 4),
        })
    # FTS OR-search often matches just one generic word ("работать" in a
    # question about fatigue, for example). Keep only strong hits; a user
    # clarification is safer than presenting an unrelated policy snippet.
    citations.sort(key=lambda c: -c["score"])
    return [citation for citation in citations
            if citation["score"] >= MIN_RELEVANCE_SCORE][:limit]


def find_by_topics(cur, topics, *, track=None, limit=4):
    rows = cur.execute(
        """
        SELECT c.id, c.doc_id, c.title, c.body, c.quote, c.topics,
               c.conflict_note, c.checklist_refs,
               d.source_type, d.url, d.version, d.freshness, d.governance,
               d.source_status, d.title AS doc_title
        FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id
        WHERE d.source_status <> 'unavailable'
          AND (d.tracks = '[]'::jsonb OR d.tracks ? 'common'
                OR (%s::text IS NOT NULL AND d.tracks ? %s))
          AND c.topics ?| %s::text[]
        ORDER BY c.id LIMIT %s
        """,
        (track, track, list(topics), limit)).fetchall()
    return [
        {
            "chunkId": r["id"], "docId": r["doc_id"], "title": r["doc_title"],
            "section": r["title"], "url": r["url"],
            "tier": TIER_BY_SOURCE_TYPE[r["source_type"]],
            "sourceType": r["source_type"], "sourceStatus": r["source_status"],
            "freshness": r["freshness"], "quote": r["quote"],
            "conflictNote": r["conflict_note"], "snippet": r["body"][:400],
            "topics": r["topics"], "checklistRefs": r["checklist_refs"],
            "score": 1.0,
        }
        for r in rows
    ]


def explain_term(cur, term, *, track=None):
    """Glossary lookup used by the explain intent: exact topic hit first,
    then FTS. Returns (citations, abstained)."""
    lowered = term.casefold()
    direct = find_by_topics(cur, [lowered], track=track, limit=2)
    hits = direct or search(cur, term, track=track, limit=3)
    return hits, not hits
