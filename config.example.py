# Your bots support server.
# * This guild ID will automatically whitelisted if whitelist mode is enabled.
# * The whitelist slash commands will also be registered to it if whitelist mode is enabled.
guild_id = 123

# Your bots user id.
client_id = "YOUR_BOT_USER_ID"

# Your bots token.
token = "YOUR_SUPER_SECRET_TOKEN_THAT_YOU_SHOULD_NEVER_SHARE"

# Whether whitelist only mode should be enabled.
whitelist = False

# The user IDs that should be able to whitelist servers.
can_whitelist = []

# Whether to leave servers that don't have the vanity feature.
only_vanity = False

# Whether to use strict matches in user statuses.
strict_vanity = False

# The PostgreSQL database URI.
postgresql = "postgresql://<user>:<password>@<host>/<database>"

# The Redis database configuration.
redis_host = "localhost"
redis_port = 6379
redis_db = 0
redis_password = None
