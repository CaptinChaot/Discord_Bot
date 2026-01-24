import os
import asyncio
import discord
import threading
import uvicorn

from api.app import create_api
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

def start_api(bot):
    app = create_api(bot)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
            
@bot.event
async def on_ready():
    print(f"✅ Eingeloggt als {bot.user} (ID: {bot.user.id})")

    #FastAPI parallel starten
    if not hasattr(bot, "_api_started"):
        bot._api_started = True

        thread  = threading.Thread(
            target=start_api,
            args=(bot,),
            daemon=True
        )
        thread.start()
        print("🌐 API-Server gestartet.")

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
