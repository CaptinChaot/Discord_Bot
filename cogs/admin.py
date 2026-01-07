import discord
from discord import app_commands
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reload", description="Reload a cog (admin)")
    @app_commands.describe(cog="z.B. fun oder admin")
    async def reload(self, interaction: discord.Interaction, cog: str):
        # Nur Admins dürfen reloaden (Testphase)
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Kein Zugriff.", ephemeral=True)
            return

        ext = f"cogs.{cog}"
        try:
            await self.bot.reload_extension(ext)
            await interaction.response.send_message(f"✅ Reloaded `{ext}`", ephemeral=True)
        except commands.ExtensionNotLoaded:
            await self.bot.load_extension(ext)
            await interaction.response.send_message(f"✅ Loaded `{ext}`", ephemeral=True)
        except commands.ExtensionError as e:
            await interaction.response.send_message(f"❌ Fehler: `{type(e).__name__}: {e}`", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))