from .vanity import Vanity
from bot import Client


async def setup(bot: Client) -> None:
    await bot.add_cog(Vanity(bot))
