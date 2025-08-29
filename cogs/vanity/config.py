from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

import discord

if TYPE_CHECKING:
    from bot import Client


class VanityConfig:
    __slots__ = (
        "guild_id",
        "custom_status",
        "award_role_id",
        "thank_you_message",
        "thank_you_channel_id",
        "log_channel_id",
        "bot",
    )

    bot: Client
    guild_id: int
    custom_status: Optional[str]
    award_role_id: Optional[int]
    thank_you_message: Optional[str]
    thank_you_channel_id: Optional[int]
    log_channel_id: Optional[int]

    @classmethod
    def from_record(cls, record: Any, bot: Client):
        self = cls()

        self.bot = bot
        self.guild_id = record["guild_id"]
        self.custom_status = record["custom_status"]
        self.award_role_id = record["award_role_id"]
        self.thank_you_message = record["thank_you_message"]
        self.thank_you_channel_id = record["thank_you_channel_id"]
        self.log_channel_id = record["log_channel_id"]

        return self

    @property
    def is_enabled(self) -> bool:
        return self.custom_status is not None

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def award_role(self) -> Optional[discord.Role]:
        if self.guild is None:
            return None
        return self.guild.get_role(self.award_role_id)

    @property
    def thank_you_channel(self) -> Optional[discord.TextChannel]:
        if self.guild is None:
            return None
        channel = self.guild.get_channel(self.thank_you_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @property
    def log_channel(self) -> Optional[discord.TextChannel]:
        if self.guild is None:
            return None
        channel = self.guild.get_channel(self.log_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None
