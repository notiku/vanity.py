from __future__ import annotations

import discord


class Colors:
    @property
    def neutral(self) -> None:
        return None

    @property
    def approve(self) -> discord.Colour:
        return discord.Colour(0xA4EB78)

    @property
    def missing(self) -> discord.Colour:
        return discord.Colour(0xFAA81A)

    @property
    def deny(self) -> discord.Colour:
        return discord.Colour(0xFF6464)

    @property
    def discord(self) -> discord.Colour:
        return discord.Colour(0x7289DA)

    @property
    def transparent(self) -> discord.Colour:
        return discord.Colour(0x2B2D31)


class Emotes:
    @property
    def approve(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(
            name="approve", id=1410319740697710723, animated=False
        )

    @property
    def deny(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="deny", id=1410319751066161202, animated=False)

    @property
    def warning(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(
            name="warning", id=1410319759836188682, animated=False
        )

    @property
    def cooldown(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(
            name="cooldown", id=1410319784670658643, animated=False
        )

    @property
    def loading(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(
            name="loading", id=1410319771328581712, animated=True
        )
