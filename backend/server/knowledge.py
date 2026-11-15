"""Deterministic, scoped PostgreSQL retrieval with source citations."""
import re

MIN_RELEVANCE_SCORE = 0.045

TIER_BY_SOURCE_TYPE = {
    "normative": "NORMATIVE",
    "reference": "PRIMARY_PLAYBOOK",
    "educational": "COURSE_SPEC",
    "public_context": "SECONDARY_PUBLIC",
}
TRACKS = ("backend", "analytics", "marketing")

_COLUMNS = """
    c.id, c.doc_id, c.title, c.body, c.quote, c.topics, c.conflict_note,
    c.checklist_refs, c.difficulty, c.estimated_minutes, d.source_type,
    d.url, d.version, d.freshness, d.source_status, d.title AS doc_title,
    d.source_locator, d.synthetic, d.tracks
"""
_SCOPE = """
    (d.tracks = '[]'::jsonb OR d.tracks ? 'common' OR d.tracks ? %(track)s)
    AND (d.roles = '[]'::jsonb OR d.roles ? 'all' OR d.roles ? %(role)s)
    AND d.source_status <> 'unavailable'
"""


def _ts_query(text):
    terms = re.findall(r"[0-9a-zа-яё]{2,}", (text or "").casefold())
    return " | ".join(list(dict.fromkeys(terms))[:12]) or None


def _citation(row):
    url = row["url"]
    return {
        "chunkId": row["id"], "docId": row["doc_id"], "title": row["doc_title"],
        "section": row["title"], "url": url if url and url.startswith("https://") else None,
        "tier": TIER_BY_SOURCE_TYPE[row["source_type"]], "sourceType": row["source_type"],
        "sourceStatus": row["source_status"], "freshness": row["freshness"],
        "quote": row["quote"], "conflictNote": row["conflict_note"],
        "snippet": row["body"][:400], "topics": row["topics"],
        "checklistRefs": row["checklist_refs"], "sourceLocator": row["source_locator"],
        "synthetic": row["synthetic"] or row["source_status"] == "reconstructed",
        "tracks": row["tracks"], "difficulty": row["difficulty"],
        "estimatedMinutes": row["estimated_minutes"], "score": round(float(row["rank"]), 4),
    }


def search(cur, query, *, track=None, role="intern", category=None, task_id=None, limit=4, min_rank=0):
    tsq = _ts_query(query)
    if not tsq:
        return []
    rows = cur.execute(
        f"""
        WITH query AS (SELECT to_tsquery('russian', %(query)s) AS terms)
        SELECT {_COLUMNS}, ts_rank(c.fts, query.terms) AS rank
        FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id CROSS JOIN query
        WHERE {_SCOPE} AND c.fts @@ query.terms
          AND ts_rank(c.fts, query.terms) >= %(min_rank)s
          AND (%(category)s::text IS NULL OR d.source_type = %(category)s)
          AND (%(task)s::text IS NULL OR c.checklist_refs ? %(task)s)
        ORDER BY rank DESC, c.id LIMIT %(limit)s
        """,
        dict(query=tsq, track=track, role=role, category=category, task=task_id, limit=limit, min_rank=min_rank),
    ).fetchall()
    return [_citation(row) for row in rows]


def find_by_topics(cur, topics, *, track=None, role="intern", limit=4):
    rows = cur.execute(
        f"""
        SELECT {_COLUMNS}, 1.0 AS rank
        FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id
        WHERE {_SCOPE} AND c.topics ?| %(topics)s::text[]
        ORDER BY c.id LIMIT %(limit)s
        """,
        dict(track=track, role=role, topics=list(topics), limit=limit),
    ).fetchall()
    return [_citation(row) for row in rows]


def explain_term(cur, term, *, track=None):
    hits = find_by_topics(cur, [term.casefold()], track=track, limit=2)
    hits = hits or search(cur, term, track=track, limit=3)
    return hits, not hits
