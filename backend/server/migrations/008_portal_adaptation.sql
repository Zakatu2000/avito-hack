ALTER TABLE portal_requests DROP CONSTRAINT portal_requests_status_check;
ALTER TABLE portal_requests ADD CONSTRAINT portal_requests_status_check
    CHECK (status IN ('draft','sent','approving','approved','rejected','in_progress',
                      'resolved','closed','awaiting_confirmation','scheduled','completed'));
ALTER TABLE portal_requests
    ADD COLUMN idempotency_key text,
    ADD COLUMN creation_payload jsonb,
    ADD COLUMN assignee_id text REFERENCES portal_accounts(user_id),
    ADD COLUMN task_id text;
CREATE UNIQUE INDEX portal_request_creation_key
    ON portal_requests(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX portal_requests_by_task ON portal_requests(user_id, task_id) WHERE task_id IS NOT NULL;
CREATE INDEX portal_grants_by_user_system ON portal_grants(user_id, system, expires_at);

ALTER TABLE portal_progress ADD COLUMN started_at timestamptz, ADD COLUMN completed_at timestamptz;
ALTER TABLE checklist_state ADD COLUMN started_at timestamptz, ADD COLUMN completed_at timestamptz;
ALTER TABLE checklist_items
    ADD COLUMN priority integer NOT NULL DEFAULT 100,
    ADD COLUMN estimated_minutes integer CHECK (estimated_minutes > 0),
    ADD COLUMN required_access jsonb NOT NULL DEFAULT '[]';
ALTER TABLE kb_chunks
    ADD COLUMN difficulty text CHECK (difficulty IN ('introductory','intermediate','advanced')),
    ADD COLUMN estimated_minutes integer CHECK (estimated_minutes > 0);
ALTER TABLE kb_documents
    ADD COLUMN source_locator text,
    ADD COLUMN synthetic boolean NOT NULL DEFAULT false;

CREATE TABLE portal_first_tasks (
    user_id text PRIMARY KEY REFERENCES portal_accounts(user_id),
    task_code text NOT NULL,
    assigned_by text NOT NULL REFERENCES portal_accounts(user_id),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    opened_at timestamptz,
    start_reported_at timestamptz,
    start_confirmed_at timestamptz
);

CREATE TABLE portal_events (
    user_id text NOT NULL REFERENCES portal_accounts(user_id),
    event_type text NOT NULL,
    entity_id text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY(user_id, event_type, entity_id)
);
CREATE INDEX portal_events_by_type ON portal_events(event_type, user_id, occurred_at);
