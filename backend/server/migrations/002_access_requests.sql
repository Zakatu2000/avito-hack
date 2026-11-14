ALTER TABLE proposals ADD COLUMN user_id text, ADD COLUMN resource_id text,
    ADD COLUMN request_id text;
ALTER TABLE access_requests ADD COLUMN user_id text, ADD COLUMN resource_id text,
    ADD COLUMN assignment_version integer;

-- The sole ticket installed by seed v1 has a known original scope. The rest
-- of the historical rows remain unbound: the assignment may have changed.
UPDATE access_requests AS t
SET user_id = 'intern-02', resource_id = 'repo-private', assignment_version = 1
FROM assignments AS a
WHERE t.id = 'req-02' AND t.assignment_id = 'task-02' AND a.id = t.assignment_id
  AND a.user_id = 'intern-02' AND a.resource_id = 'repo-private' AND a.version = 1
  AND EXISTS (SELECT 1 FROM demo_seeds WHERE version = 'b2-v1');

CREATE UNIQUE INDEX one_active_access_request
    ON access_requests (user_id, resource_id)
    WHERE status IN ('pending', 'approved');

-- Both foreign keys include scope, so cross-user/key and cross-resource
-- mappings cannot be introduced even by a competing caller.
ALTER TABLE access_requests ADD UNIQUE (id, user_id, resource_id);
ALTER TABLE proposals ADD UNIQUE (id, user_id),
    ADD FOREIGN KEY (request_id, user_id, resource_id)
    REFERENCES access_requests(id, user_id, resource_id);
CREATE TABLE confirmation_keys (
    user_id text NOT NULL,
    key_hash bytea NOT NULL,
    proposal_id text NOT NULL,
    PRIMARY KEY (user_id, key_hash),
    FOREIGN KEY (proposal_id, user_id) REFERENCES proposals(id, user_id) ON DELETE CASCADE
);

CREATE FUNCTION bind_access_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    scope assignments%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.id, NEW.assignment_id, NEW.user_id, NEW.resource_id, NEW.assignment_version)
            IS DISTINCT FROM
           (OLD.id, OLD.assignment_id, OLD.user_id, OLD.resource_id, OLD.assignment_version) THEN
            RAISE EXCEPTION 'Immutable access scope' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO STRICT scope FROM assignments WHERE id = NEW.assignment_id FOR SHARE;
    IF (NEW.user_id IS NOT NULL AND NEW.user_id <> scope.user_id)
        OR (NEW.resource_id IS NOT NULL AND NEW.resource_id <> scope.resource_id)
        OR (NEW.assignment_version IS NOT NULL AND NEW.assignment_version <> scope.version) THEN
        RAISE EXCEPTION 'Assignment scope has changed' USING ERRCODE = '23514';
    END IF;
    NEW.user_id := scope.user_id;
    NEW.resource_id := scope.resource_id;
    NEW.assignment_version := scope.version;
    RETURN NEW;
END $$;

CREATE TRIGGER bind_proposal_scope BEFORE INSERT OR UPDATE ON proposals
    FOR EACH ROW EXECUTE FUNCTION bind_access_scope();
CREATE TRIGGER bind_ticket_scope BEFORE INSERT OR UPDATE ON access_requests
    FOR EACH ROW EXECUTE FUNCTION bind_access_scope();

CREATE FUNCTION preserve_proposal_result() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.request_id IS NOT NULL AND NEW.request_id IS DISTINCT FROM OLD.request_id THEN
        RAISE EXCEPTION 'A confirmed proposal already has a result' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER preserve_proposal_result BEFORE UPDATE OF request_id ON proposals
    FOR EACH ROW EXECUTE FUNCTION preserve_proposal_result();

-- Ensure a proposal cannot become valid again after its assignment moves away
-- and returns, even when the caller omitted an explicit version increment.
CREATE FUNCTION advance_assignment_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.version < OLD.version THEN
        RAISE EXCEPTION 'Assignment version cannot decrease' USING ERRCODE = '23514';
    END IF;
    IF (NEW.user_id, NEW.resource_id, NEW.title, NEW.source_id) IS DISTINCT FROM
       (OLD.user_id, OLD.resource_id, OLD.title, OLD.source_id) AND NEW.version = OLD.version THEN
        NEW.version := OLD.version + 1;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER advance_assignment_version BEFORE UPDATE ON assignments
    FOR EACH ROW EXECUTE FUNCTION advance_assignment_version();
