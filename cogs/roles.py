from utils.logger import logger, log_to_channel

import discord
from discord import app_commands
from discord.ext import commands
from utils.config import config


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_permission(self, member: discord.Member) -> bool:
        admin_id = int(config.roles.get("admin", 0))
        mod_id = int(config.roles.get("moderator", 0))

        return any(
            role.id in (admin_id, mod_id)
            for role in member.roles
        )

    @app_commands.command(name="role_add", description="Rolle zuweisen")
    async def role_add(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: discord.Role,
    ):
        if not self._has_permission(interaction.user):
            await interaction.response.send_message(
                "❌ Keine Berechtigung.",
                ephemeral=True,
            )
            return

        if role in user.roles:
            await interaction.response.send_message(
                "⚠️ User hat die Rolle bereits.",
                ephemeral=True,
            )
            return

        # 🔴 HIER passiert die Aktion
        await user.add_roles(
            role,
            reason=f"Role add by {interaction.user}",
        )

        # 🟢 HIER kommt das Logging (GENAU HIER)
        logger.info(
            f"ROLE ADD | {interaction.user} -> {user} | {role.id}:{role.name}"
        )

        await log_to_channel(
            self.bot,
            int(config.log_channels.get("bot", 0)),
            "🟢 Rolle hinzugefügt",
            f"**Moderator:** {interaction.user.mention}\n"
            f"**User:** {user.mention}\n"
            f"**Rolle:** {role.mention}",
            discord.Color.green(),
        )

        # 🔵 Zum Schluss Antwort an den Command-User
        await interaction.response.send_message(
            f"✅ {role.mention} zu {user.mention} hinzugefügt.",
            ephemeral=True,
        )

    @app_commands.command(name="role_remove", description="Rolle entfernen")
    async def role_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: discord.Role,
    ):
        if not self._has_permission(interaction.user):
            await interaction.response.send_message(
                "❌ Keine Berechtigung.",
                ephemeral=True,
            )
            return

        if role not in user.roles:
            await interaction.response.send_message(
                "⚠️ User hat diese Rolle nicht.",
                ephemeral=True,
            )
            return

        # 🔴 Aktion
        await user.remove_roles(
            role,
            reason=f"Role remove by {interaction.user}",
        )

        # 🟢 Logging DIREKT DANACH
        logger.info(
            f"ROLE REMOVE | {interaction.user} -> {user} | {role.id}:{role.name}"
        )

        await log_to_channel(
            self.bot,
            int(config.log_channels.get("bot", 0)),
            "🔴 Rolle entfernt",
            f"**Moderator:** {interaction.user.mention}\n"
            f"**User:** {user.mention}\n"
            f"**Rolle:** {role.mention}",
            discord.Color.red(),
        )

        # 🔵 Antwort
        await interaction.response.send_message(
            f"✅ {role.mention} von {user.mention} entfernt.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
