from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from .config import VanityConfig
from cogs.utils import cache
from discord.ext import commands
from discord import app_commands
import discord

if TYPE_CHECKING:
    from bot import Client
    from cogs.utils.context import GuildContext


class Vanity(commands.Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @cache.cache(maxsize=1024, strategy=cache.Strategy.lru)
    async def get_guild_config(self, guild_id: int) -> Optional[VanityConfig]:
        query = """SELECT * FROM vanity_config WHERE guild_id = $1"""
        async with self.bot.pool.acquire(timeout=300.0) as con:
            record = await con.fetchrow(query, guild_id)
            if record is not None:
                return VanityConfig.from_record(record, self.bot)
            return None

    async def send_log(
        self, config: VanityConfig, member: discord.Member, removed: bool
    ) -> None:
        channel = config.log_channel
        if channel is not None:
            embed = discord.Embed(
                color=self.bot.colors.deny if removed else self.bot.colors.approve,
                description=f"{member.name} {'no longer has' if removed else 'has'} vanity in the custom status ({member.id})",
            )
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    async def send_thank_you(
        self, config: VanityConfig, member: discord.Member
    ) -> None:
        if config.thank_you_channel is None or config.thank_you_message is None:
            return

        key = f"vanity:thankyou:{member.guild.id}:{member.id}"
        if await self.bot.redis.get(key):
            return
        await self.bot.redis.set(key, 1, ex=30)

        channel = config.thank_you_channel
        text = config.thank_you_message.format(user=member, guild=member.guild)
        if channel is not None:
            try:
                await channel.send(text)
            except Exception:
                pass

    async def award_role(
        self, config: VanityConfig, member: discord.Member, removed: bool
    ) -> None:
        if config.award_role is None:
            return

        role = config.award_role
        if role is not None:
            if removed:
                try:
                    await member.remove_roles(role, reason="Vanity role")
                except Exception:
                    pass
            else:
                if role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Vanity role")
                    except Exception:
                        pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        config = await self.get_guild_config(member.guild.id)
        if config is None or not config.is_enabled:
            return

        if not isinstance(member.activity, discord.CustomActivity):
            return

        has_vanity = (
            self.bot.config.strict_vanity
            and member.activity.name == config.custom_status
            or not self.bot.config.strict_vanity
            and member.activity.name
            and config.custom_status in member.activity.name
        )
        if not has_vanity:
            return

        await self.send_log(config, member, removed=False)
        await self.send_thank_you(config, member)
        await self.award_role(config, member, removed=False)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return

        config = await self.get_guild_config(member.guild.id)
        if config is None or not config.is_enabled:
            return

        if not isinstance(member.activity, discord.CustomActivity):
            return

        had_vanity = (
            self.bot.config.strict_vanity
            and member.activity.name == config.custom_status
            or not self.bot.config.strict_vanity
            and member.activity.name
            and config.custom_status in member.activity.name
        )
        if not had_vanity:
            return

        await self.send_log(config, member, removed=True)

    @commands.Cog.listener()
    async def on_presence_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        if before.bot or after.bot:
            return

        config = await self.get_guild_config(after.guild.id)
        if config is None or not config.is_enabled:
            return

        before_has_status = (
            isinstance(before.activity, discord.CustomActivity)
            and self.bot.config.strict_vanity
            and before.activity.name == config.custom_status
            or isinstance(before.activity, discord.CustomActivity)
            and not self.bot.config.strict_vanity
            and before.activity.name
            and config.custom_status in before.activity.name
        )
        after_has_status = (
            isinstance(after.activity, discord.CustomActivity)
            and self.bot.config.strict_vanity
            and after.activity.name == config.custom_status
            or isinstance(after.activity, discord.CustomActivity)
            and not self.bot.config.strict_vanity
            and after.activity.name
            and config.custom_status in after.activity.name
        )

        if before_has_status and not after_has_status:
            await self.send_log(config, after, removed=True)
            await self.award_role(config, after, removed=True)
        elif not before_has_status and after_has_status:
            await self.send_log(config, after, removed=False)
            await self.send_thank_you(config, after)
            await self.award_role(config, after, removed=False)

    @commands.hybrid_group(name="vanity", aliases=["vn"], hidden=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def vanity(self, ctx: GuildContext) -> None:
        """Vanity management commands."""
        await ctx.show_help()

    @vanity.command(name="status", hidden=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(status="The custom status to track.")
    async def vanity_status(
        self, ctx: GuildContext, status: Optional[str] = None
    ) -> None:
        """Set or remove the custom status to track."""

        if status is None:
            query = """
            UPDATE vanity_config SET custom_status = NULL WHERE guild_id = $1
            """
            await self.bot.pool.execute(query, ctx.guild.id)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve("Removed the **custom status**.")
            return

        if len(status) > 80:
            await ctx.missing("Status must be at most **80 characters** long.")
            return

        query = """
        INSERT INTO vanity_config (guild_id, custom_status) VALUES ($1, $2)
        ON CONFLICT (guild_id) DO UPDATE SET custom_status = $2
        """
        await self.bot.pool.execute(query, ctx.guild.id, status)
        self.get_guild_config.invalidate(ctx.guild.id)
        await ctx.approve(f"Set the **custom status** to: `{status}`")

    @vanity.command(name="role", hidden=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(role="The role to award.")
    async def vanity_role(
        self, ctx: GuildContext, role: Optional[discord.Role] = None
    ) -> None:
        """Set or remove the award role."""

        if role is None:
            query = """
            UPDATE vanity_config SET award_role_id = NULL WHERE guild_id = $1
            """
            await self.bot.pool.execute(query, ctx.guild.id)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve("Removed the **award role**.")
            return

        query = """
        INSERT INTO vanity_config (guild_id, award_role_id) VALUES ($1, $2)
        ON CONFLICT (guild_id) DO UPDATE SET award_role_id = $2
        """
        await self.bot.pool.execute(query, ctx.guild.id, role.id)
        self.get_guild_config.invalidate(ctx.guild.id)
        await ctx.approve(f"Set the **award role** to: {role.mention}")

    @vanity.command(name="channel", hidden=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel to send messages to.")
    async def vanity_channel(
        self, ctx: GuildContext, channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Set or remove the channel to send thank you messages to."""

        if channel is None:
            query = """
            UPDATE vanity_config SET thank_you_channel_id = NULL WHERE guild_id = $1
            """
            await self.bot.pool.execute(query, ctx.guild.id)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve("Removed the **thank you channel**.")
            return
        else:
            query = """
            INSERT INTO vanity_config (guild_id, thank_you_channel_id) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET thank_you_channel_id = $2
            """
            await self.bot.pool.execute(query, ctx.guild.id, channel.id)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve(f"Set the **thank you channel** to: {channel.mention}")

    @vanity.command(name="log", hidden=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel to send logs to.")
    async def vanity_log(
        self, ctx: GuildContext, channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Set or remove the channel to send logs to."""

        if channel is None:
            query = """
            UPDATE vanity_config SET log_channel_id = NULL WHERE guild_id = $1
            """
            await self.bot.pool.execute(query, ctx.guild.id)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve("Removed the **log channel**.")
            return
        else:
            query = """
            INSERT INTO vanity_config (guild_id, log_channel_id) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET log_channel_id = $2
            """
            await self.bot.pool.execute(query, ctx.guild.id, channel.id)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve(f"Set the **log channel** to: {channel.mention}")

    @vanity.command(name="message", hidden=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(message="The message to send.")
    async def vanity_message(
        self, ctx: GuildContext, message: Optional[str] = None
    ) -> None:
        """Set or remove the thank you message to send."""

        if message is None:
            query = """
            UPDATE vanity_config SET thank_you_message = NULL WHERE guild_id = $1
            """
            await self.bot.pool.execute(query, ctx.guild.id)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve("Removed the **thank you message**.")
            return
        else:
            query = """
            INSERT INTO vanity_config (guild_id, thank_you_message) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET thank_you_message = $2
            """
            await self.bot.pool.execute(query, ctx.guild.id, message)
            self.get_guild_config.invalidate(ctx.guild.id)
            await ctx.approve("Set the **thank you message**")

    @vanity.command(name="reset", hidden=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def vanity_reset(self, ctx: GuildContext) -> None:
        """Reset and disable the vanity configuration."""

        query = """
        DELETE FROM vanity_config WHERE guild_id = $1
        """
        await self.bot.pool.execute(query, ctx.guild.id)
        self.get_guild_config.invalidate(ctx.guild.id)
        await ctx.approve("Reset the **vanity** settings.")
