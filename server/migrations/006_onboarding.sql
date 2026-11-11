-- Onboarding domain: intern profiles, normalized checklist catalog and runtime
-- state, versioned knowledge base, typed actions with HITL/idempotency/audit,
-- learning records, competency assessments and episodic memory.
-- Owns no access rights: the legacy access flow (001-005) stays authoritative.

CREATE TABLE intern_profiles (
    user_id text PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    track text NOT NULL CHECK (track IN ('backend', 'analytics', 'marketing')),
    role_code text NOT NULL,
    grade text NOT NULL,
    week_no integer NOT NULL DEFAULT 1 CHECK (week_no BETWEEN 1 AND 52),
    start_date date NOT NULL DEFAULT CURRENT_DATE,
    mentor_name text NOT NULL DEFAULT '',
    curator_name text NOT NULL DEFAULT '',
    unit text NOT NULL DEFAULT ''
);

CREATE TABLE checklist_items (
    id text PRIMARY KEY,
    track text NOT NULL,
    title text NOT NULL,
    original_text text NOT NULL,
    description text NOT NULL DEFAULT '',
    instructions jsonb NOT NULL DEFAULT '[]',
    stage text NOT NULL,
    stage_order integer NOT NULL,
    stage_label text NOT NULL,
    actor text NOT NULL DEFAULT 'intern' CHECK (actor IN ('intern', 'mentor', 'curator')),
    prerequisites jsonb NOT NULL DEFAULT '[]',
    objective text NOT NULL DEFAULT '',
    evidence text NOT NULL DEFAULT '',
    completion_policy text NOT NULL DEFAULT 'self_confirmed'
        CHECK (completion_policy IN ('self_confirmed', 'evidence_required', 'curator_confirmed')),
    source_ref jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX checklist_items_by_track ON checklist_items (track, stage_order, id);

-- Lifecycle: available -> in_progress -> evidence_pending -> completed,
-- or blocked (prerequisite unmet / waiting on a human).
CREATE TABLE checklist_state (
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id text NOT NULL REFERENCES checklist_items(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'in_progress', 'evidence_pending', 'completed', 'blocked')),
    evidence_uri text,
    note text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE kb_documents (
    id text PRIMARY KEY,
    title text NOT NULL,
    source_type text NOT NULL
        CHECK (source_type IN ('normative', 'reference', 'educational', 'public_context')),
    url text,
    version text NOT NULL,
    freshness text,
    tracks jsonb NOT NULL DEFAULT '[]',
    roles jsonb NOT NULL DEFAULT '[]',
    governance text NOT NULL DEFAULT '',
    source_status text NOT NULL DEFAULT 'verified'
        CHECK (source_status IN ('verified', 'reconstructed', 'unavailable'))
);

CREATE TABLE kb_chunks (
    id text PRIMARY KEY,
    doc_id text NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    title text NOT NULL,
    body text NOT NULL,
    quote text NOT NULL DEFAULT '',
    topics jsonb NOT NULL DEFAULT '[]',
    conflict_note text,
    checklist_refs jsonb NOT NULL DEFAULT '[]',
    fts tsvector GENERATED ALWAYS AS (
        to_tsvector('russian', title || ' ' || body || ' ' || quote)
    ) STORED
);
CREATE INDEX kb_chunks_fts ON kb_chunks USING gin (fts);
CREATE INDEX kb_chunks_by_doc ON kb_chunks (doc_id);

-- Typed actions: preview (draft) -> confirm -> execute exactly once -> audit.
CREATE TABLE pending_actions (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type text NOT NULL
        CHECK (action_type IN ('send_message', 'access_request', 'reminder',
                               'meeting', 'checklist_evidence', 'escalation',
                               'development_plan')),
    payload jsonb NOT NULL,
    checklist_item_id text REFERENCES checklist_items(id),
    idempotency_key text NOT NULL,
    confirmation_token text NOT NULL,
    status text NOT NULL DEFAULT 'draft_preview'
        CHECK (status IN ('draft_preview', 'confirmed', 'executed', 'cancelled', 'failed')),
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX pending_actions_idem
    ON pending_actions (user_id, idempotency_key) WHERE status <> 'cancelled';
CREATE INDEX pending_actions_by_user ON pending_actions (user_id, created_at DESC);

CREATE TABLE action_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    action_id text,
    event text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX action_audit_by_user ON action_audit (user_id, id DESC);

CREATE TABLE learning_records (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id text REFERENCES checklist_items(id),
    kind text NOT NULL CHECK (kind IN ('note', 'quiz', 'evidence', 'explanation')),
    payload jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX learning_records_by_user ON learning_records (user_id, id DESC);

CREATE TABLE competency_assessments (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track text NOT NULL,
    ratings jsonb NOT NULL,
    priorities jsonb NOT NULL DEFAULT '[]',
    plan jsonb NOT NULL DEFAULT '[]',
    evidence jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX competency_by_user ON competency_assessments (user_id, created_at DESC);

-- Mock curator messenger: inbound replies are pasted by the intern (or pushed
-- by the demo operator) and parsed into decisions/actions.
CREATE TABLE curator_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    direction text NOT NULL CHECK (direction IN ('in', 'out')),
    channel text NOT NULL DEFAULT 'curator',
    body text NOT NULL,
    parsed jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX curator_messages_by_user ON curator_messages (user_id, id DESC);

-- Episodic memory: compressed running summary owned by the server, never the LLM.
CREATE TABLE conversation_memory (
    user_id text PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    summary text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now()
);
