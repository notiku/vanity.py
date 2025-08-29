from .whitelist import Whitelist
from bot import Client
import config


async def setup(bot: Client) -> None:
    if config.whitelist:
        await bot.add_cog(Whitelist(bot))
