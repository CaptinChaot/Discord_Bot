# utils/tickets/views.py

import discord
from discord.ui import View, Select, Modal, TextInput, Button

from utils.tickets.constants import TICKET_TYPES


class TicketDescriptionModal(Modal):
    def __init__(self, ticket_type: str):
        super().__init__(title="Ticket erstellen")
        self.ticket_type = ticket_type

        self.description = TextInput(
            label="Beschreibe dein Problem",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1500,
        )
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        # Übergabe an Cog (keine Logik hier!)
        interaction.ticket_data = {
            "type": self.ticket_type,
            "description": self.description.value,
        }
        await interaction.response.defer(ephemeral=True)


class TicketTypeSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Wähle die Art deines Tickets aus …",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=data["label"],
                    description=data["description"],
                    value=key
                )
                for key, data in TICKET_TYPES.items()
            ],
            custom_id="ticket_type_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            TicketDescriptionModal(self.values[0])
        )


class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


class TicketClaimButton(Button):
    def __init__(self):
        super().__init__(label="Claim", style=discord.ButtonStyle.primary, emoji="🖐", custom_id="ticket_claim")


class TicketCloseButton(Button):
    def __init__(self):
        super().__init__(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")


class TicketChannelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketClaimButton())
        self.add_item(TicketCloseButton())
