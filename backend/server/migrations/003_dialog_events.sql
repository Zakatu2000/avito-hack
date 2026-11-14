CREATE TABLE onboarding_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assignment_id text NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    name text NOT NULL CHECK (name IN ('blocker_reported', 'request_created')),
    request_id text REFERENCES access_requests(id) ON DELETE CASCADE,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((name = 'request_created') = (request_id IS NOT NULL))
);
CREATE UNIQUE INDEX first_blocker_report ON onboarding_events(assignment_id)
    WHERE name = 'blocker_reported';
CREATE UNIQUE INDEX one_request_event ON onboarding_events(request_id)
    WHERE name = 'request_created';

CREATE FUNCTION record_new_request() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO onboarding_events(assignment_id, name, request_id)
    VALUES (NEW.assignment_id, 'request_created', NEW.id);
    RETURN NEW;
END $$;
CREATE TRIGGER record_new_request AFTER INSERT ON access_requests
    FOR EACH ROW WHEN (NEW.status = 'pending') EXECUTE FUNCTION record_new_request();
