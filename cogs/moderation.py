import discord

from datetime import timedelta
from discord import app_commands, Interaction
from discord.ext import commands
from utils.config import config
from utils.logger import logger, log_to_channel
from discord.utils import utcnow
from utils.checks import has_mod_permissions
from utils.warnings_db import (
    add_warning,
    count_warnings,
    delete_warnings as db_delete_warnings
)





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

    @app_commands.command(name="warn",description="Verwarnt einen User und loggt es im Modlog")
    @app_commands.describe(
        user="User, der verwarnt werden soll",
        reason="Grund für die Verwarnung"
    )
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return

        # Selbstschutz
        if user == interaction.user:
            await interaction.followup.send(
                "❌ Du kannst dich nicht selbst verwarnen.",
                ephemeral=True
            )
            return

        # DM an User (optional, aber Standard)
        try:
            await user.send(
                f"⚠️ **Verwarnung auf {interaction.guild.name}**\n"
                f"**Grund:** {reason}\n"
                f"**Moderator:** {interaction.user}"
            )
        except discord.Forbidden:
            pass  # DMs aus → egal, Log zählt

        # Warnung in DB speichern
        add_warning(
            guild_id=interaction.guild.id,
            user_id=user.id,
            moderator_id=interaction.user.id,
            reason=reason,
        )
        # Anzahl der Verwarnungen holen
        total_warnings = count_warnings(
            guild_id=interaction.guild.id,
            user_id=user.id
        )
        # Modlog Embed
        embed = discord.Embed(
            title="⚠️ Verwarnung",
            color=discord.Color.orange(),
            timestamp=utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Anzahl der Verwarnungen", value=str(total_warnings), inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user}", inline=False)
        embed.add_field(name="Grund", value=reason, inline=False)

        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id != 0:
            modlog_channel = self.bot.get_channel(channel_id)
            if modlog_channel:
                await modlog_channel.send(embed=embed)
        await interaction.followup.send(
            f"✅ {user.mention} wurde verwarnt.",
            ephemeral=True
        )

    @app_commands.command(name="warnings", description="Zeigt die Anzahl der Verwarnungen eines Users an")
    @app_commands.describe(
        user="User, dessen Verwarnungen angezeigt werden sollen"
    )  

    async def warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return
        if user.bot:
            await interaction.followup.send(
                "❌ Bots können keine Verwarnungen haben.",
                ephemeral=True
            )
            return
        
        # Anzahl der Verwarnungen holen
        total_warnings = count_warnings(
            guild_id=interaction.guild.id,
            user_id=user.id
        )

        await interaction.followup.send(
            f"ℹ️ {user.mention} hat {total_warnings} Verwarnung(en).",
            ephemeral=True
        )

    @app_commands.command(name="delete_warnings", description="Löscht alle Verwarnungen eines Users")
    @app_commands.describe(
        user="User, dessen Verwarnungen gelöscht werden sollen"
    )
    async def delete_warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return
        if user.bot:
            await interaction.followup.send(
                "❌ Bots können keine Verwarnungen haben.",
                ephemeral=True
            )
            return
        
        # Verwarnungen löschen
        db_delete_warnings(
            guild_id=interaction.guild.id,
            user_id=user.id
        )

        await interaction.followup.send(
            f"✅ Alle Verwarnungen von {user.mention} wurden gelöscht.",
            ephemeral=True
        )
async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))


