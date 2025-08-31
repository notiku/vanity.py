from __future__ import annotations

from cogs.utils.constants import Emotes, Colors
from cogs.utils.context import Context
from discord.ext import commands
import discord
import datetime
import logging
import aiohttp
from typing import Any, Optional, Union
from collections import defaultdict

import config
import asyncpg
import redis.asyncio as redis


description = """
A Discord bot for rewarding users for representing your servers vanity in their status.
"""

log = logging.getLogger(__name__)

initial_extensions = (
    "cogs.dev",
    "cogs.vanity",
)


# This is never used as the bot currently only uses slash commands.
def _prefix_callable(bot: Client, msg: discord.Message):
    user_id = bot.user.id
    base = [f"<@!{user_id}> ", f"<@{user_id}> "]
    if msg.guild is None:
        base.append(",")
    return base


class ProxyObject(discord.Object):
    def __init__(self, guild: Optional[discord.abc.Snowflake]):
        super().__init__(id=0)
        self.guild: Optional[discord.abc.Snowflake] = guild


class Client(commands.AutoShardedBot):
    user: discord.ClientUser
    pool: asyncpg.Pool
    redis: redis.Redis
    logging_handler: Any
    bot_app_info: discord.AppInfo

    def __init__(self):
        allowed_mentions = discord.AllowedMentions(
            everyone=False, users=True, roles=False, replied_user=False
        )
        intents = discord.Intents(
            guilds=True,
            members=True,
            presences=True,
        )
        super().__init__(
            command_prefix=_prefix_callable,
            description=description,
            chunk_guilds_at_startup=True,
            heartbeat_timeout=150.0,
            allowed_mentions=allowed_mentions,
            intents=intents,
            enable_debug_events=True,
        )

        self.client_id: str = config.client_id

        # shard_id: List[datetime.datetime]
        # shows the last attempted IDENTIFYs and RESUMEs
        self.resumes: defaultdict[int, list[datetime.datetime]] = defaultdict(list)
        self.identifies: defaultdict[int, list[datetime.datetime]] = defaultdict(list)

        # Constants
        self.colors = Colors()
        self.emotes = Emotes()

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()

        self.tree.interaction_check = self.interaction_check

        self.bot_app_info = await self.application_info()
        if not self.bot_app_info.team:
            self.owner_id = self.bot_app_info.owner.id
        else:
            if len(self.bot_app_info.team.members) == 1:
                self.owner_id = self.bot_app_info.team.members[0].id
            else:
                self.owner_ids = [m.id for m in self.bot_app_info.team.members]

        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception:
                log.exception("Failed to load extension %s.", extension)

    @property
    def owner(self) -> discord.User:
        if self.bot_app_info.team:
            return self.get_user(self.bot_app_info.team.members[0].id)  # type: ignore
        return self.bot_app_info.owner

    def _clear_gateway_data(self) -> None:
        one_week_ago = discord.utils.utcnow() - datetime.timedelta(days=7)
        for shard_id, dates in self.identifies.items():
            to_remove = [index for index, dt in enumerate(dates) if dt < one_week_ago]
            for index in reversed(to_remove):
                del dates[index]

        for shard_id, dates in self.resumes.items():
            to_remove = [index for index, dt in enumerate(dates) if dt < one_week_ago]
            for index in reversed(to_remove):
                del dates[index]

    async def before_identify_hook(self, shard_id: int, *, initial: bool):
        self._clear_gateway_data()
        self.identifies[shard_id].append(discord.utils.utcnow())
        await super().before_identify_hook(shard_id, initial=initial)

    async def on_command_error(
        self, ctx: Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.UserNotFound):
            await ctx.missing(
                "I was unable to find that **member** or the **ID** is invalid"
            )
        elif isinstance(error, commands.MemberNotFound):
            await ctx.missing(
                f"I was unable to find a member with the name: **{error.argument}**"
            )
        elif isinstance(error, commands.RoleNotFound):
            await ctx.missing(
                f"I was unable to find a role with the name: **{error.argument}**"
            )
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.missing(
                f"I was unable to find a channel with the name: **{error.argument}**"
            )
        elif isinstance(error, commands.MaxConcurrencyReached):
            return
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.cooldown(
                f"Please wait **{error.retry_after:.2f}** seconds before using this command again",
                ephemeral=True,
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help()
        elif isinstance(error, commands.BadArgument):
            await ctx.error(str(error).replace('"', "**").replace(".", ""))
        elif isinstance(error, commands.BadUnionArgument):
            await ctx.missing(str(error).replace('"', "**").replace(".", ""))
        elif isinstance(error, commands.MissingPermissions):
            missing_perms = []
            for perm in error.missing_permissions:
                missing_perms.append(f"`{perm}`")
            await ctx.missing(
                f"You're **missing** permission{'' if len(error.missing_permissions) == 1 else 's'}: {', '.join(missing_perms)}"
            )
        elif isinstance(error, commands.BotMissingPermissions):
            missing_perms = []
            for perm in error.missing_permissions:
                missing_perms.append(f"`{perm}`")
            await ctx.missing(
                f"I'm **missing** permission{'' if len(error.missing_permissions) == 1 else 's'}: {', '.join(missing_perms)}"
            )
        elif isinstance(error, commands.NoPrivateMessage):
            return
        elif isinstance(error, commands.CheckFailure):
            return
        else:
            log.exception(f"Exception in command {ctx.command.qualified_name}: {error}")

    async def on_ready(self):
        if not hasattr(self, "uptime"):
            self.uptime = discord.utils.utcnow()

            if config.only_vanity:
                for guild in self.guilds:
                    if discord.utils.get(guild.features, name="VANITY_URL") is None:
                        try:
                            await guild.leave()
                        except Exception:
                            log.warning(
                                "Failed to leave guild %s: %s", guild.id, exc_info=True
                            )

        log.info("Ready: %s (ID: %s)", self.user, self.user.id)

    async def on_shard_resumed(self, shard_id: int):
        log.info("Shard ID %s has resumed...", shard_id)
        self.resumes[shard_id].append(discord.utils.utcnow())

    async def get_context(
        self, origin: Union[discord.Interaction, discord.Message], /, *, cls=Context
    ) -> Context:
        return await super().get_context(origin, cls=cls)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.is_ready():
            return False

        if (
            config.whitelist
            and interaction.guild is not None
            and not await self.redis.get(f"whitelist:{interaction.guild.id}")
        ):
            return False

        return True

    async def process_commands(self, message: discord.Message):
        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        await self.process_commands(message)

    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        if (
            after.author.bot
            or after.content == before.content
            or before.created_at
            <= discord.utils.utcnow() - datetime.timedelta(seconds=30)
        ):
            return
        await self.process_commands(after)

    async def on_guild_join(self, guild: discord.Guild):
        if not config.only_vanity:
            return

        has_vanity_feature = (
            discord.utils.get(guild.features, name="VANITY_URL") is not None
        )

        if not has_vanity_feature:
            try:
                await guild.leave()
            except Exception:
                log.warning("Failed to leave guild %s: %s", guild.id, exc_info=True)

    async def close(self) -> None:
        await super().close()
        await self.session.close()

    async def start(self) -> None:
        await super().start(config.token, reconnect=True)

    @property
    def config(self):
        return __import__("config")
