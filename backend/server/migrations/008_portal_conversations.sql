-- Persistent AI-buddy conversations per portal account (additive; existing
-- tables and data are untouched).
CREATE TABLE portal_conversations (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES portal_accounts(user_id),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX portal_conversations_user ON portal_conversations(user_id, updated_at DESC);

CREATE TABLE portal_messages (
    id bigserial PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES portal_conversations(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'bot')),
    text text NOT NULL CHECK (length(text) BETWEEN 1 AND 8000),
    actions jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX portal_messages_conversation ON portal_messages(conversation_id, id);
