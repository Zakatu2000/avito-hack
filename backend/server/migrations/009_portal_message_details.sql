ALTER TABLE portal_messages ADD COLUMN reply jsonb NOT NULL DEFAULT '{}';
CREATE INDEX portal_reply_message_id ON portal_messages ((reply->>'messageId'))
    WHERE reply ? 'messageId';
