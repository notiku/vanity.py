from __future__ import annotations
from typing import TYPE_CHECKING, Any, Iterable, Protocol, TypeVar, Union, Optional

from discord.ext import commands
import discord

if TYPE_CHECKING:
    from bot import Client
    from aiohttp import ClientSession
    from asyncpg import Pool, Connection
    from types import TracebackType


T = TypeVar("T")


class ConnectionContextManager(Protocol):
    async def __aenter__(self) -> Connection: ...

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None: ...


class DatabaseProtocol(Protocol):
    async def execute(
        self, query: str, *args: Any, timeout: Optional[float] = None
    ) -> str: ...

    async def fetch(
        self, query: str, *args: Any, timeout: Optional[float] = None
    ) -> list[Any]: ...

    async def fetchrow(
        self, query: str, *args: Any, timeout: Optional[float] = None
    ) -> Optional[Any]: ...

    def acquire(
        self, *, timeout: Optional[float] = None
    ) -> ConnectionContextManager: ...

    def release(self, connection: Connection) -> None: ...


class ConfirmationView(discord.ui.View):
    def __init__(
        self, bot: Client, *, timeout: float, author_id: int, delete_after: bool
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot: Client = bot
        self.value: Optional[bool] = None
        self.delete_after: bool = delete_after
        self.author_id: int = author_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            embed = discord.Embed(
                color=self.bot.colors.missing,
                description=f"{self.bot.emotes.warning} You're not the **author** of this embed!",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        if self.delete_after and self.message:
            await self.message.delete()

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()

        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()

        self.stop()


class Context(commands.Context):
    channel: Union[
        discord.VoiceChannel, discord.TextChannel, discord.Thread, discord.DMChannel
    ]
    prefix: str
    command: commands.Command[Any, ..., Any]
    bot: Client

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pool: Pool = self.bot.pool

    async def entry_to_code(self, entries: Iterable[tuple[str, str]]) -> None:
        width = max(len(a) for a, b in entries)
        output = ["```"]
        for name, entry in entries:
            output.append(f"{name:<{width}}: {entry}")
        output.append("```")
        await self.send("\n".join(output))

    async def indented_entry_to_code(self, entries: Iterable[tuple[str, str]]) -> None:
        width = max(len(a) for a, b in entries)
        output = ["```"]
        for name, entry in entries:
            output.append(f"\u200b{name:>{width}}: {entry}")
        output.append("```")
        await self.send("\n".join(output))

    def __repr__(self) -> str:
        # we need this for our cache key strategy
        return "<Context>"

    @property
    def session(self) -> ClientSession:
        return self.bot.session

    @discord.utils.cached_property
    def replied_reference(self) -> Optional[discord.MessageReference]:
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved.to_reference()
        return None

    @discord.utils.cached_property
    def replied_message(self) -> Optional[discord.Message]:
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved
        return None

    async def prompt(
        self,
        message: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        *,
        timeout: float = 60.0,
        delete_after: bool = True,
        ephemeral: bool = False,
        author_id: Optional[int] = None,
    ) -> Optional[bool]:
        """An interactive reaction confirmation dialog.

        Parameters
        -----------
        message: str
            The message to show along with the prompt.
        timeout: float
            How long to wait before returning.
        delete_after: bool
            Whether to delete the confirmation message after we're done.
        ephemeral: bool
            Wheter the the confirmation menu should be ephemeral. (interaction commands only)
        author_id: Optional[int]
            The member who should respond to the prompt. Defaults to the author of the
            Context's message.

        Returns
        --------
        Optional[bool]
            ``True`` if explicit confirm,
            ``False`` if explicit deny,
            ``None`` if deny due to timeout
        """

        if message is None and embed is None:
            raise ValueError("Prompt requires a message or embed.")

        author_id = author_id or self.author.id
        view = ConfirmationView(
            self.bot,
            timeout=timeout,
            delete_after=delete_after,
            author_id=author_id,
        )
        embeds = [embed] if embed else []
        view.message = await self.send(
            message, embeds=embeds, view=view, ephemeral=ephemeral
        )
        await view.wait()
        return view.value

    async def embed(
        self,
        description: str,
        color: Union[int, discord.Color, discord.Colour, None] = None,
        emoji: Union[str, discord.PartialEmoji, None] = None,
        message: Optional[str] = None,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        embed = discord.Embed(
            color=color,
            description=f"{str(emoji) + ' ' if emoji else ''}{self.author.mention}: {description}",
        )

        try:
            return await self.send(message, embed=embed, ephemeral=ephemeral)
        except (discord.HTTPException, discord.Forbidden, ValueError, TypeError):
            return None

    async def approve(
        self, description: str, message: str = None, ephemeral: bool = False
    ) -> Optional[discord.Message]:
        return await self.embed(
            description,
            message=message,
            ephemeral=ephemeral,
            color=self.bot.colors.approve,
            emoji=self.bot.emotes.approve,
        )

    async def missing(
        self, description: str, message: str = None, ephemeral: bool = False
    ) -> Optional[discord.Message]:
        return await self.embed(
            description,
            message=message,
            ephemeral=ephemeral,
            color=self.bot.colors.missing,
            emoji=self.bot.emotes.warning,
        )

    async def error(
        self, description: str, message: str = None, ephemeral: bool = False
    ) -> Optional[discord.Message]:
        return await self.embed(
            description,
            message=message,
            ephemeral=ephemeral,
            color=self.bot.colors.missing,
            emoji=self.bot.emotes.warning,
        )

    async def neutral(
        self,
        description: str,
        emoji: Union[str, discord.PartialEmoji, None] = None,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        return await self.embed(
            description, ephemeral=ephemeral, color=self.bot.colors.neutral, emoji=emoji
        )

    async def discord(
        self,
        description: str,
        emoji: Union[str, discord.PartialEmoji, None] = None,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        return await self.embed(
            description, ephemeral=ephemeral, color=self.bot.colors.discord, emoji=emoji
        )

    async def cooldown(
        self, description: str, ephemeral: bool = False
    ) -> Optional[discord.Message]:
        return await self.embed(
            description,
            ephemeral=ephemeral,
            color=0x50C7EF,
            emoji=self.bot.emotes.cooldown,
        )

    async def tick(self, message: discord.Message = None) -> bool:
        return await self.safe_react(
            "\N{WHITE HEAVY CHECK MARK}", message or self.message
        )

    @property
    def db(self) -> DatabaseProtocol:
        return self.pool  # type: ignore

    async def show_help(self, command: Any = None) -> None:
        pass

    async def safe_react(self, reaction: str, message: discord.Message = None) -> bool:
        """Safely adds a reaction to the message."""

        msg = message or self.message

        try:
            await msg.add_reaction(str(reaction))
            return True
        except discord.HTTPException:
            pass

        return False


class GuildContext(Context):
    author: discord.Member
    guild: discord.Guild
    channel: Union[discord.VoiceChannel, discord.TextChannel, discord.Thread]
    me: discord.Member
    prefix: str
