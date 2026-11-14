ALTER TABLE onboarding_events DROP CONSTRAINT onboarding_events_name_check;
ALTER TABLE onboarding_events ADD CONSTRAINT onboarding_events_name_check
    CHECK (name IN ('blocker_reported', 'request_created', 'access_granted', 'task_link_opened'));
ALTER TABLE onboarding_events DROP CONSTRAINT onboarding_events_check;
ALTER TABLE onboarding_events ADD CONSTRAINT onboarding_events_request_check
    CHECK ((name IN ('request_created', 'access_granted')) = (request_id IS NOT NULL));
CREATE UNIQUE INDEX one_grant_event ON onboarding_events(request_id)
    WHERE name = 'access_granted';
