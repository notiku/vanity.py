from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar

from discord.ext import commands

if TYPE_CHECKING:
    from .context import Context, GuildContext

T = TypeVar("T")


async def check_permissions(ctx: GuildContext, perms: dict[str, bool], *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    resolved = ctx.channel.permissions_for(ctx.author)
    return check(
        getattr(resolved, name, None) == value for name, value in perms.items()
    )


def has_permissions(*, check=all, **perms: bool):
    async def pred(ctx: GuildContext):
        return await check_permissions(ctx, perms, check=check)

    return commands.check(pred)


async def check_guild_permissions(
    ctx: GuildContext, perms: dict[str, bool], *, check=all
):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.guild is None:
        return False

    resolved = ctx.author.guild_permissions
    return check(
        getattr(resolved, name, None) == value for name, value in perms.items()
    )


def has_guild_permissions(*, check=all, **perms: bool):
    async def pred(ctx: GuildContext):
        return await check_guild_permissions(ctx, perms, check=check)

    return commands.check(pred)


def can_whitelist():
    async def predicate(ctx: Context) -> bool:
        is_owner = await ctx.bot.is_owner(ctx.author)
        if is_owner:
            return True

        if ctx.author.id in ctx.bot.config.can_whitelist:
            return True

        return False

    return commands.check(predicate)
