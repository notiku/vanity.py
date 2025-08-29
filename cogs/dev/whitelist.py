from __future__ import annotations
from typing import TYPE_CHECKING, Union

from cogs.utils import checks
from discord.ext import commands, tasks
from discord import app_commands
import discord
import datetime
import config

if TYPE_CHECKING:
    from bot import Client
    from cogs.utils.context import Context


class Whitelist(commands.Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.whitelisted_guild_ids: list[int] = []

    async def fetch_whitelisted_guild_ids(self) -> list[int]:
        await self.bot.pool.execute(
            "INSERT INTO whitelist (guild_id, user_id, whitelister_id) VALUES ($1, $2, $3) ON CONFLICT (guild_id) DO NOTHING",
            self.bot.config.guild_id,
            self.bot.user.id,
            self.bot.user.id,
        )

        records = await self.bot.pool.fetch("SELECT guild_id FROM whitelist")
        guild_ids: list[int] = [record["guild_id"] for record in records]

        for guild_id in guild_ids:
            await self.bot.redis.set(f"whitelist:{guild_id}", 1)

        return guild_ids

    async def get_whitelisted_guild_ids(self) -> list[int]:
        keys = await self.bot.redis.keys("whitelist:*")
        guild_ids: list[int] = [int(key.decode().split(":")[1]) for key in keys]

        return guild_ids

    async def leave_unauthorized(self) -> None:
        for guild in self.bot.guilds:
            if guild.id not in self.whitelisted_guild_ids:
                await guild.leave()

    async def cog_load(self) -> None:
        self.whitelisted_guild_ids = await self.fetch_whitelisted_guild_ids()
        self.update_whitelist.start()

    def cog_unload(self) -> None:
        self.update_whitelist.cancel()

    @tasks.loop(hours=1)
    async def update_whitelist(self) -> None:
        self.whitelisted_guild_ids = await self.get_whitelisted_guild_ids()

    @update_whitelist.before_loop
    async def before_update_whitelist(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.leave_unauthorized()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        is_whitelisted = guild.id in self.whitelisted_guild_ids
        if not is_whitelisted:
            await guild.leave()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        pass

    @commands.hybrid_group(name="whitelist", aliases=["wl"], hidden=True)
    @checks.can_whitelist()
    @app_commands.guilds(config.guild_id)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def whitelist(self, ctx: Context) -> None:
        """Whitelist management commands."""
        await ctx.show_help()

    @whitelist.command(name="add", hidden=True)
    @checks.can_whitelist()
    @app_commands.guilds(config.guild_id)
    @app_commands.describe(
        guild="The guild id you want to whitelist.",
        user="The user who requested the whitelist.",
    )
    async def whitelist_add(
        self, ctx: Context, guild: str, user: Union[discord.Member, discord.User]
    ) -> None:
        """Add a guild to the whitelist."""

        if await self.bot.redis.get(f"whitelist:{guild}"):
            await ctx.error(f"There's already a whitelist for `{guild}`")
            return

        try:
            guild_id = int(guild)
        except ValueError:
            await ctx.error(f"Invalid guild ID: `{guild}`")
            return

        query = """
        INSERT INTO whitelist (guild_id, user_id, whitelister_id)
        VALUES ($1, $2, $3) ON CONFLICT (guild_id) DO NOTHING
        """

        await self.bot.pool.execute(query, guild_id, user.id, ctx.author.id)
        await self.bot.redis.set(f"whitelist:{guild_id}", 1)
        if guild_id not in self.whitelisted_guild_ids:
            self.whitelisted_guild_ids.append(guild_id)

        await ctx.approve(f"Success, added **{guild_id}** to the whitelist")

    @whitelist.command(name="delete", aliases=["del", "remove"], hidden=True)
    @checks.can_whitelist()
    @app_commands.guilds(config.guild_id)
    @app_commands.describe(
        guild="The guild id you want to whitelist.",
    )
    async def whitelist_delete(self, ctx: Context, guild: str) -> None:
        """Remove a guild from the whitelist."""

        if ctx.guild and guild == str(ctx.guild.id):
            await ctx.missing("You should remove the guild from another server")
            return

        if not await self.bot.redis.get(f"whitelist:{guild}"):
            await ctx.error(f"I couldn't find a whitelist for `{guild}`")
            return

        try:
            guild_id = int(guild)
        except ValueError:
            await ctx.error(f"Invalid guild ID: `{guild}`")
            return

        query = """
        DELETE FROM whitelist WHERE guild_id = $1
        """

        await self.bot.pool.execute(query, guild_id)
        await self.bot.redis.delete(f"whitelist:{guild_id}")
        if guild_id in self.whitelisted_guild_ids:
            self.whitelisted_guild_ids.pop(guild_id)

        _guild = self.bot.get_guild(guild_id)
        if _guild is not None:
            await _guild.leave()

        await ctx.approve(f"Success, removed **{guild_id}** from the whitelist")

    @whitelist.command(name="transfer", aliases=["move"], hidden=True)
    @checks.can_whitelist()
    @app_commands.guilds(config.guild_id)
    @app_commands.describe(
        guild="The guild id you want to transfer the whitelist from.",
        new_guild="The guild id you want to transfer the whitelist to.",
    )
    async def whitelist_transfer(
        self, ctx: Context, guild: str, new_guild: str
    ) -> None:
        """Transfer a guild's whitelist to another guild."""

        try:
            guild_id = int(guild)
        except ValueError:
            await ctx.error(f"Invalid guild ID: `{guild}`")
            return

        try:
            new_guild_id = int(new_guild)
        except ValueError:
            await ctx.error(f"Invalid guild ID: `{new_guild}`")
            return

        if await self.bot.redis.get(f"whitelist:{new_guild_id}"):
            await ctx.error(f"There's already a whitelist for `{new_guild_id}`")
            return

        if not await self.bot.redis.get(f"whitelist:{guild_id}"):
            await ctx.error(f"I couldn't find a whitelist for `{guild_id}`")
            return

        query = """
        UPDATE whitelist SET guild_id = $2, transfers = transfers + 1
        WHERE guild_id = $1
        """

        await self.bot.pool.execute(query, guild_id, new_guild_id)
        await self.bot.redis.delete(f"whitelist:{guild_id}")
        if guild_id in self.whitelisted_guild_ids:
            self.whitelisted_guild_ids.remove(guild_id)

        _guild = self.bot.get_guild(guild_id)
        if _guild is not None:
            await _guild.leave()

        await self.bot.redis.set(f"whitelist:{new_guild_id}", 1)
        if new_guild_id not in self.whitelisted_guild_ids:
            self.whitelisted_guild_ids.append(new_guild_id)

        await ctx.approve(
            f"Success, transferred whitelist from **{guild_id}** to **{new_guild_id}**"
        )

    @whitelist.command(name="info", hidden=True)
    @checks.can_whitelist()
    @app_commands.guilds(config.guild_id)
    @app_commands.describe(
        guild="The guild id you want to view whitelist information from.",
    )
    async def whitelist_info(self, ctx: Context, guild: str) -> None:
        """View a guild's whitelist information."""

        try:
            guild_id = int(guild)
        except ValueError:
            await ctx.error(f"Invalid guild ID: `{guild}`")
            return

        query = """
        SELECT user_id, whitelister_id, created_at
        FROM whitelist WHERE guild_id = $1
        """

        record = await self.bot.pool.fetchrow(query, guild_id)
        if not record:
            await ctx.error(f"I couldn't find a whitelist for `{guild_id}`")
            return

        user_id: int = record["user_id"]
        user = self.bot.get_user(user_id)
        user_name = user.name if user else "Unknown"
        whitelister_id: int = record["whitelister_id"]
        whitelister = self.bot.get_user(whitelister_id)
        whitelister_name = whitelister.name if whitelister else "Unknown"
        created_at: datetime.datetime = record["created_at"].replace(
            tzinfo=datetime.timezone.utc
        )
        created_at_timestamp: int = round(created_at.timestamp())

        _guild = self.bot.get_guild(guild_id)
        guild_name = _guild.name if _guild else "Server"

        embed = discord.Embed(
            title="**Whitelist**",
            description=f"{guild_name} was whitelisted on <t:{created_at_timestamp}:F> (<t:{created_at_timestamp}:R>)",
        )
        embed.set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )
        embed.add_field(
            name="**User**",
            value=f"**User**: {user_name}\n**ID**: `{user_id}`",
            inline=True,
        )
        embed.add_field(
            name="**Whitelister**",
            value=f"**User**: {whitelister_name}\n**ID**: `{whitelister_id}`",
            inline=True,
        )

        await ctx.send(embed=embed)
