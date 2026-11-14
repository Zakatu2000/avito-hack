-- Additive integration schema. Legacy users, sessions and API remain usable.
CREATE TABLE portal_accounts (
    user_id text PRIMARY KEY REFERENCES users(id),
    email text NOT NULL UNIQUE CHECK (email = lower(email)),
    name text NOT NULL,
    role text NOT NULL DEFAULT 'intern' CHECK (role IN ('intern', 'mentor', 'lead')),
    team text NOT NULL DEFAULT 'Platform Interns'
);
CREATE TABLE portal_progress (
    user_id text NOT NULL REFERENCES portal_accounts(user_id),
    item_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('not_started','in_progress','pending_approval','done')),
    PRIMARY KEY (user_id, item_id)
);
CREATE TABLE portal_requests (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES portal_accounts(user_id),
    status text NOT NULL CHECK (status IN ('draft','sent','approving','approved','rejected')),
    data jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE portal_grants (
    request_id text PRIMARY KEY REFERENCES portal_requests(id),
    user_id text NOT NULL REFERENCES portal_accounts(user_id),
    system text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE TABLE portal_auth_limits (
    bucket text PRIMARY KEY,
    attempts integer NOT NULL,
    expires_at timestamptz NOT NULL
);
