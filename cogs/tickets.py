# cogs/tickets.py

import discord
from discord.ext import commands

from utils.tickets.views import TicketPanelView, TicketChannelView
from utils.tickets.manager import create_ticket_channel, claim_ticket, archive_ticket


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Persistent Views nach Restart:
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketChannelView())

    @commands.command(name="send_ticket_panel")
    @commands.has_permissions(administrator=True)
    async def send_ticket_panel(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🎫 Ticketsystem",
            description=(
                "Bitte wähle aus, **wobei wir dir helfen können**.\n\n"
                "➡️ Danach beschreibst du dein Problem\n"
                "➡️ Ein privater Ticket-Channel wird erstellt"
            ),
            color=discord.Color.blurple()
        )

        await ctx.send(embed=embed, view=TicketPanelView())

    @send_ticket_panel.error
    async def send_ticket_panel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Dafür fehlen dir die Rechte.")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # 1) Ticket Creation (kommt aus Modal)
        if hasattr(interaction, "ticket_data"):
            try:
                ch = await create_ticket_channel(
                    bot=self.bot,
                    guild=interaction.guild,
                    user=interaction.user,
                    ticket_type=interaction.ticket_data["type"],
                    description=interaction.ticket_data["description"],
                )
                # Startmessage mit Claim/Close View ergänzen (letzte Bot-Message im Channel)
                await ch.send("Support kann das Ticket jetzt claimen/close'n:", view=TicketChannelView())

                await interaction.followup.send(f"✅ Ticket erstellt: {ch.mention}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Ticket konnte nicht erstellt werden: {type(e).__name__}: {e}", ephemeral=True)
            return

        # 2) Claim / Close Buttons
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id")

            # Claim
            if cid == "ticket_claim":
                await interaction.response.defer(ephemeral=True)
                try:
                    await claim_ticket(
                        bot=self.bot,
                        channel=interaction.channel,
                        claimer=interaction.user
                    )
                    await interaction.followup.send("✅ Ticket geclaimed.", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ Claim fehlgeschlagen: {type(e).__name__}: {e}", ephemeral=True)
                return

            # Close/Archive
            if cid == "ticket_close":
                await interaction.response.defer(ephemeral=True)
                try:
                    await archive_ticket(
                        bot=self.bot,
                        channel=interaction.channel,
                        closed_by=interaction.user
                    )
                    await interaction.followup.send("🗂 Ticket wurde archiviert.", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ Close fehlgeschlagen: {type(e).__name__}: {e}", ephemeral=True)
                return


async def setup(bot):
    await bot.add_cog(Tickets(bot))
