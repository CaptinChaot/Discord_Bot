import os
import asyncio
import discord

from discord.ext import commands
from dotenv import load_dotenv
from utils.logger import logger, log_to_channel
from utils.config import config
from discord import app_commands
from utils.warnings_db import init_db

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

TEST_GUILD_ID = config.guild_id  # dein Testserver

intents = discord.Intents.default()
intents.message_content = False

init_db()

class ChaosBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",  # Dummy Command Prefix
            intents=intents,
            help_command=None,
        )
    async def setup_hook(self):
        # Cogs laden
        await self.load_extension("cogs.admin")
        await self.load_extension("cogs.fun")
        await self.load_extension("cogs.roles")
        await self.load_extension("cogs.moderation")

        # Slash Commands instant auf Testserver
        guild = discord.Object(id=TEST_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

bot = ChaosBot()

@bot.event
async def on_ready():
    print(f"✅ Eingeloggt als {bot.user} (ID: {bot.user.id})")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN fehlt in .env")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):

    root_error = getattr(error, "original", error)
    if isinstance(root_error, app_commands.CheckFailure):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
        return
    
    logger.error(f"Fehler bei Slash Command: {root_error}")
    if interaction.response.is_done():
        return

    await interaction.response.send_message(
    "❌ Ein interner Fehler ist aufgetreten.",
    ephemeral=True
)
bot.run(TOKEN)
