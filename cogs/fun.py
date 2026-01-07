import discord
from discord import app_commands
from discord.ext import commands

class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Bot ping test")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong ✅", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
