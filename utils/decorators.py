import functools
import discord
from discord import app_commands
from utils.permissions import has_permission


def require_perm(action: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                raise app_commands.CheckFailure("Kein Guild-Kontext")

            if not has_permission(interaction.user, action):
                raise app_commands.CheckFailure("Keine Berechtigung")

            return await func(self, interaction, *args, **kwargs)

        return wrapper
    return decorator
