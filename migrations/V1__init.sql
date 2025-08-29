-- Revises: V0
-- Creation Date: 2025-08-25 18:04:38.039909 UTC
-- Reason: init

CREATE TABLE IF NOT EXISTS whitelist (
    guild_id BIGINT NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    whitelister_id BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (now() at time zone 'utc')
);

CREATE INDEX IF NOT EXISTS idx_whitelist_user_id ON whitelist (user_id);

CREATE TABLE IF NOT EXISTS vanity_config (
    guild_id BIGINT NOT NULL PRIMARY KEY,
    custom_status TEXT,
    award_role_id BIGINT,
    thank_you_message TEXT,
    thank_you_channel_id BIGINT,
    log_channel_id BIGINT
);
