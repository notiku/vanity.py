# Vanity.py

A Discord bot for rewarding users for representing your servers vanity in their status.

## How does it work?

When a member has a set text in their custom status they'll be awarded an optional role set the by the server and the bot will send an optional thank you message to a set a channel, that's pretty much it.

## Features

- Option to run in "whitelist" mode.
  - ⚠️ This will make the bot leave **EVERY** server it is in or is being invited to unless manually whitelisted.
  - Note: The set `guild_id` in config.py will always be whitelisted.

- Option to switch between strict and not strict matching
  - Setting `vanity_strict` to `True` in config.py will make the bot check if the users status is equal to the set one, just checks if it's somewhere in the status otherwise.

- Option to automatically leave servers that don't have the vanity feature.

## How do I self-host it?

- Make sure you already have at least Python 3.11 installed on your system.
- Make sure you have PostgreSQL installed and a user and database with the `pg_trgm` extension setup.
- Make sure you have Redis installed and `appendonly` enabled.

- Clone the repository and cd into it.
  - `git clone https://github.com/notiku/vanity.py`
  - `cd vanity.py`

- Create a virtual env.
  - `python3 -m venv venv` on Linux or `py -m venv venv` on Windows.
  - `source venv/bin/activate` on Linux or `.\venv\Scripts\activate.bat` on Windows.

- Install the requirements.
  - `pip install -r requirements.txt`

- Setup the config.
  - Fill in the values in `config.example.py` and rename it to `config.py`

- Initialize the database.
  - Note: From now on use `python` on Linux and replace it with `py` on Windows.
  - `python launcher.py db init`

- Register slash commands.
  - `python launcher.py slash`

- And finally, start the bot.
  - `python launcher.py`

## How do I change the embeds?

To change the bots colors and emojis used accross all embeds edit them in [cogs/utils/constants.py](/cogs/utils/constants.py).

## TODO

The bot is pretty much done as there isn't really much to it other than adding a role to users that "rep" a server and send a message so don't expect many feature updates.

We're working on a "mini" version that runs with a JSON "database" (or none at all) to make self-hosting for people that only want to use the bot for their personal server easier.

Maybe add support for other activity types?

## Privacy Policy and Terms of Service

No personal data is stored.
