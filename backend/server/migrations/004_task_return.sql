ALTER TABLE onboarding_events DROP CONSTRAINT onboarding_events_name_check;
ALTER TABLE onboarding_events ADD CONSTRAINT onboarding_events_name_check
    CHECK (name IN ('blocker_reported', 'request_created', 'task_link_opened'));
CREATE UNIQUE INDEX first_task_return ON onboarding_events(assignment_id)
    WHERE name = 'task_link_opened';
