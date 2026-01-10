import discord

from datetime import timedelta
from discord import app_commands, Interaction
from discord.ext import commands
from utils.config import config
from utils.logger import logger, log_to_channel
from discord.utils import utcnow
from utils.checks import has_mod_permissions



class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @app_commands.command(name="timeout", description="Setze einen User in Timeout")
    async def timeout(self, interaction: Interaction, user: discord.Member, duration: int, reason: str = "Kein Grund angegeben"):
        await interaction.response.defer(ephemeral=True)
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
        "❌ Du hast keine Berechtigung, diesen Befehl zu nutzen.",
        ephemeral=True
    )
            return
        if duration <= 0:
            await interaction.followup.send(
                "❌ Dauer muss größer als 0 sein.",
            ephemeral=True
    )
            return


        until = utcnow() + timedelta(seconds=duration)
        await user.timeout(until, reason=reason)
        channel_id = int(config.log_channels.get("moderation", 0)) # 0 = kein Logging - durch config.yaml wird geguckt obs nen log_channel gibt
        if channel_id != 0:
            await log_to_channel(
                 self.bot,
                channel_id,
                f"⏱️ Timeout gesetzt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})"
                f"**User:** {user.mention} (ID: {user.id})\n"
                f"**Dauer:** {duration} Sekunden\n"
                f"**Grund:** {reason}\n",
                discord.Color.red(),
                )
        logger.info(
    f"TIMEOUT | {interaction.user} -> {user} | {duration}s | {reason}"
)

        await interaction.followup.send(
            f"✅ {user.mention} wurde für {duration} Sekunden in Timeout gesetzt. Grund: {reason}",
            ephemeral=True
        )

    @app_commands.command(name="untimeout", description="Entferne den Timeout von einem User")
    async def untimeout(self, interaction: Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
        "❌ Du hast keine Berechtigung, diesen Befehl zu nutzen.",
        ephemeral=True
    )
            return

        await user.timeout(None, reason="Timeout entfernt durch Moderation")
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id != 0:
                await log_to_channel(
                    self.bot,
                    channel_id,
                    f"⏱️ Timeout entfernt",
                    f"**Moderator:** {interaction.user} (ID: {interaction.user.id})"
                    f"**User:** {user.mention} (ID: {user.id})\n",
                    discord.Color.green(),
                )
        logger.info(f"UNTIMEOUT | {interaction.user} -> {user}")
        await interaction.followup.send(
            f"✅ Timeout von {user.mention} wurde entfernt.",
            ephemeral=True
        )
async def setup(bot): #immer NUR 1  IN CODE PRO COG
    await bot.add_cog(Moderation(bot)) 
