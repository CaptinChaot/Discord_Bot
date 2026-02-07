# cogs/dev.py

from discord.ext import commands

class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="tickets_reload")
    @commands.is_owner()
    async def tickets_reload(self, ctx):
        await self.bot.reload_extension("cogs.tickets")
        await ctx.send("♻️ Ticketsystem neu geladen")

async def setup(bot):
    await bot.add_cog(Dev(bot))
