import functools
import discord
from utils.permissions import get_user_perm_level, PermLevel
from utils.config import config


def require_perm(action: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):

            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    "❌ Dieser Befehl kann hier nicht verwendet werden.",
                    ephemeral=True
                )
                return

            perm_cfg = config.permissions.get(action)
            if not perm_cfg:
                await interaction.response.send_message(
                    "❌ Dieser Befehl ist falsch konfiguriert.",
                    ephemeral=True
                )
                return

            required_level = PermLevel[perm_cfg["min_level"]]
            user_level = get_user_perm_level(interaction.user)

            if user_level < required_level:
                await interaction.response.send_message(
                    "❌ Keine Berechtigung.",
                    ephemeral=True
                )
                return

            return await func(self, interaction, *args, **kwargs)

        return wrapper
    return decorator
