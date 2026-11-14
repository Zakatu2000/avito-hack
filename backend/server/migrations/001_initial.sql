CREATE TABLE teams (
    id text PRIMARY KEY
);

CREATE TABLE users (
    id text PRIMARY KEY,
    username text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    role text NOT NULL CHECK (role IN ('intern', 'operator')),
    team_id text NOT NULL REFERENCES teams(id)
);

CREATE TABLE resources (
    id text PRIMARY KEY,
    team_id text NOT NULL REFERENCES teams(id)
);

CREATE TABLE instructions (
    id text PRIMARY KEY,
    team_id text NOT NULL REFERENCES teams(id),
    excerpt text NOT NULL
);

CREATE TABLE assignments (
    id text PRIMARY KEY,
    user_id text NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    resource_id text NOT NULL REFERENCES resources(id),
    source_id text REFERENCES instructions(id),
    title text NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0)
);

CREATE TABLE access_grants (
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_id text NOT NULL REFERENCES resources(id),
    PRIMARY KEY (user_id, resource_id)
);

CREATE TABLE proposals (
    id text PRIMARY KEY,
    assignment_id text NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    assignment_version integer NOT NULL CHECK (assignment_version > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE access_requests (
    id text PRIMARY KEY,
    assignment_id text NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX access_requests_by_assignment
    ON access_requests (assignment_id, created_at DESC, id DESC);

CREATE TABLE sessions (
    token_hash text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);
CREATE INDEX sessions_by_user ON sessions(user_id);

CREATE TABLE demo_seeds (
    version text PRIMARY KEY,
    installed_at timestamptz NOT NULL DEFAULT now()
);
