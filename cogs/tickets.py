import discord
from discord.ext import commands
from discord import app_commands

from utils.tickets.views import TicketPanelView
from utils.permissions import get_user_perm_level, PermLevel


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================
    # /send_ticket_panel (DEV/OWNER)
    # =========================

    @app_commands.command(
        name="send_ticket_panel",
        description="Sendet das Ticket-Panel (DEV/OWNER only)"
    )
    async def send_ticket_panel(self, interaction: discord.Interaction):
        # ---- Permission Check (DEIN System) ----
        if get_user_perm_level(interaction.user) < PermLevel.DEV:
            await interaction.response.send_message(
                "❌ Dafür hast du keine Berechtigung.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎫 Ticketsystem",
            description=(
                "Bitte wähle aus, **wobei wir dir helfen können**.\n\n"
                "➡️ Wähle eine Kategorie\n"
                "➡️ Beschreibe dein Problem\n"
                "➡️ Ein privater Ticket-Channel wird erstellt"
            ),
            color=discord.Color.blurple()
        )

        await interaction.channel.send(
            embed=embed,
            view=TicketPanelView()
        )

        await interaction.response.send_message(
            "✅ Ticket-Panel wurde gesendet.",
            ephemeral=True
        )

    # =========================
    # Sync (nur Owner, optional)
    # =========================

    @app_commands.command(
        name="sync_tickets",
        description="Synchronisiert Ticket Slash Commands (OWNER)"
    )
    async def sync_tickets(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "❌ Nur der Server-Owner.",
                ephemeral=True
            )
            return

        await self.bot.tree.sync(guild=interaction.guild)
        await interaction.response.send_message(
            "✅ Ticket-Slash-Commands synchronisiert.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
