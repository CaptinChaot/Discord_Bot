import discord

from datetime import timedelta
from discord import app_commands, Interaction
from discord.ext import commands
from utils.hardlock import hardlock_check, hardlock_log_line
from utils.hardening import can_moderate
from utils.config import config
from utils.logger import logger, log_to_channel
from discord.utils import utcnow
from utils.moderation_utils import can_auto_action, handle_auto_actions
from utils.decorators import require_perm
from utils.warnings_db import (
    add_warning, count_warnings, delete_warnings as db_delete_warnings,
    delete_warning_by_id, get_last_warning_id,get_last_auto_action, save_ban,save_timeout, clear_ban, clear_timeout)
from utils.moderation_actions import (safe_timeout, safe_untimeout, safe_kick, safe_ban, safe_unban)





mod_cfg = config.moderation

timeout_warn = mod_cfg.get("warn_timeout_threshold", 2)
timeout_duration = mod_cfg.get("warn_timeout_duration", 300)
kick_warn = mod_cfg.get("warn_kick_threshold", 3)
ban_warn = mod_cfg.get("warn_ban_threshold", 5)



class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @app_commands.command(name="timeout", description="Setze einen User in Timeout")
    @require_perm("timeout")
    async def timeout(self, interaction: Interaction, user: discord.Member, duration: int, reason: str = "Kein Grund angegeben"):
        await interaction.response.defer(ephemeral=True)

        # Hardlock Check
        allowed, block_reason = hardlock_check(interaction, user)
        if not allowed:
            logger.warning(hardlock_log_line(interaction, user, block_reason))
            await interaction.followup.send(
                f"❌ {block_reason}",
                ephemeral=True
            )
            return
        
        #--- Action Helpers ---
        ok, error = await safe_timeout(
            user, duration, reason=reason
        )
        if not ok:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True
            )
            return
        until = utcnow() + timedelta(seconds=duration)
        save_timeout(interaction.guild_id, user.id, until, reason)
        # Loggen   
        channel_id = int(config.log_channels.get("moderation", 0)) # 0 = kein Logging - durch config.yaml wird geguckt obs nen log_channel gibt
        if channel_id:
            await log_to_channel(
                self.bot,
                channel_id,
                f"⏱️ Timeout gesetzt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User:** {user.mention} (ID: {user.id})\n"
                f"**Dauer:** {duration} Sekunden\n"
                f"**Grund:** {reason}\n",
                discord.Color.gold(),
                )
        logger.info(
    f"TIMEOUT | {interaction.user} -> {user} | {duration}s | {reason}"
        )

        await interaction.followup.send(
            f"✅ {user.mention} wurde für {duration} Sekunden in Timeout gesetzt. Grund: {reason}",
            ephemeral=True
        )

    @app_commands.command(name="untimeout", description="Entferne den Timeout von einem User")
    @app_commands.describe(
        user="User, dessen Timeout entfernt werden soll",
        reason="Grund für das Entfernen des Timeouts")
    @require_perm("untimeout")
    async def untimeout(self, interaction: Interaction, user: discord.Member, reason: str = "Timeout entfernt durch Moderator"):
        await interaction.response.defer(ephemeral=True)

        # Hardlock Check
        allowed, block_reason = hardlock_check(interaction, user)
        if not allowed:
            logger.warning(hardlock_log_line(interaction, user, block_reason))
            await interaction.followup.send(
                f"❌ {block_reason}",
                ephemeral=True
            )
            return
        #--- Action Helpers ---
        ok, error = await safe_untimeout(user, reason=reason)
        if not ok:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True
            )
            return
        clear_timeout(interaction.guild.id, user.id)
        # Loggen
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
                await log_to_channel(
                    self.bot,
                    channel_id,
                    f"⏱️ Timeout entfernt",
                    f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                    f"**User:** {user.mention} (ID: {user.id})\n",
                    discord.Color.green(),
                )
        logger.info(f"UNTIMEOUT | {interaction.user} -> {user}")
        await interaction.followup.send(
            f"✅ Timeout von {user.mention} wurde entfernt.\n",
            f"**Grund:** {reason}",
            ephemeral=True
        )

    @app_commands.command(name="warn",description="Verwarnt einen User und loggt es im Modlog")
    @app_commands.describe(
        user="User, der verwarnt werden soll",
        reason="Grund für die Verwarnung"
    )
    @require_perm("warn")
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str
    ):
        await interaction.response.defer(ephemeral=True)

        allowed, reason = can_moderate(interaction=interaction, target=user, action="warn")
        if not allowed:
            await interaction.followup.send(
                f"❌ {reason}",
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

        # --- Automatische Maßnahmen ---
        if can_auto_action(interaction, user):
            action_taken = await handle_auto_actions(
                bot=self.bot,
                interaction=interaction,
                user=user,
                total_warnings=total_warnings,
                timeout_warn=timeout_warn,
                kick_warn=kick_warn,
                ban_warn=ban_warn,
                timeout_duration=timeout_duration
            )
            if action_taken:
                return  # Auto-Aktion 
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
        if channel_id:
            await log_to_channel(self.bot,channel_id,"⚠️ User verwarnt",embed=embed)
        await interaction.followup.send(
        f"✅ {user.mention} wurde verwarnt.",
        ephemeral=True
    )

    @app_commands.command(name="warnings", description="Zeigt die Anzahl der Verwarnungen eines Users an")
    @app_commands.describe(
        user="User, dessen Verwarnungen angezeigt werden sollen"
    )  
    @require_perm("warnings")
    async def warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)
    
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
    @require_perm("del_warnings")
    async def delete_warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        allowed, reason = can_moderate(interaction=interaction, target=user, action="del_warnings")
        if not allowed:
            await interaction.followup.send(
                f"❌ {reason}",
                ephemeral=True
            )
            return
        
        if user.bot:
            await interaction.followup.send(
                "❌ Bots können keine Verwarnungen haben.",
                ephemeral=True
            )
            return        
        # Anzahl VOR dem Löschen holen
        total_warnings = count_warnings(
            guild_id=interaction.guild.id,
            user_id=user.id
            )

        # Wenn es nichts zu löschen gibt
        if total_warnings == 0:
            await interaction.followup.send(
                f"ℹ️ {user.mention} hat keine Verwarnungen.",
                ephemeral=True
            )
            return
        # Verwarnungen löschen
        db_delete_warnings(
            guild_id=interaction.guild.id,
            user_id=user.id
        )

        embed = discord.Embed(
            title="🧹 Verwarnungen gelöscht",
            color=discord.Color.orange(),
            timestamp=utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Anzahl gelöscht", value=str(total_warnings), inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user}", inline=False)

        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            modlog_channel = self.bot.get_channel(channel_id)
            if modlog_channel:
                await modlog_channel.send(embed=embed)
        # EINMAL antworten
        await interaction.followup.send(
            f"✅ Alle Verwarnungen von {user.mention} wurden gelöscht.",
            ephemeral=True
        )
    @app_commands.command(name="unwarn", description="Löscht die letzte Verwarnung eines Users")
    @app_commands.describe(
        user="User, dessen letzte Verwarnung gelöscht werden soll"
    )
    @require_perm("warn")
    async def unwarn(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        allowed, reason = can_moderate(interaction=interaction, target=user, action="unwarn")
        if not allowed:
            await interaction.followup.send(
                f"❌ {reason}",
                ephemeral=True
            )
            return

        # Letzte Verwarnung ID holen
        warn_id = get_last_warning_id(
            guild_id=interaction.guild.id,
            user_id=user.id
        )
        if warn_id is None:
            await interaction.followup.send(
                f" {user.mention} hat keine Verwarnungen.",
                ephemeral=True
            )
            return
        
        # Letzte Verwarnung löschen
        delete_warning_by_id(warn_id)

        embed = discord.Embed(
            title="🧹 Letzte Verwarnung gelöscht",
            color=discord.Color.orange(),
            timestamp=utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user}", inline=False)    

        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            modlog_channel = self.bot.get_channel(channel_id)
            if modlog_channel:
                await modlog_channel.send(embed=embed)

        await interaction.followup.send(
            f"✅ Die letzte Verwarnung von {user.mention} wurde gelöscht.",
            ephemeral=True
            )

    @app_commands.command(name="kick", description="Kickt einen User aus dem Server")
    @app_commands.describe(
        user="User, der gekickt werden soll",
        reason="Grund für den Kick"
    )
    @require_perm("kick")
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "Kein Grund angegeben"
    ):
        await interaction.response.defer(ephemeral=True)

         # Hardlock Check
        allowed, block_reason = hardlock_check(interaction, user)
        if not allowed:
            logger.warning(hardlock_log_line(interaction, user, block_reason))
            await interaction.followup.send(
                f"❌ {block_reason}",
                ephemeral=True
            )
            return
        #--- Action Helpers ---
        ok, error = await safe_kick(
            user, reason=reason
        )
        if not ok:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True
            )
            return
        # Loggen
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            await log_to_channel(
                self.bot,
                channel_id,
                f"👢 User gekickt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User:** {user.mention} (ID: {user.id})\n"
                f"**Grund:** {reason}\n",
                discord.Color.orange(),
            )
        logger.info(f"KICK | {interaction.user} -> {user} | {reason}")

        await interaction.followup.send(
            f"✅ {user.mention} wurde gekickt. Grund: {reason}",
            ephemeral=True
        )

    @app_commands.command(name="ban", description="Bannt einen User vom Server")
    @app_commands.describe(
        user="User, der gebannt werden soll",
        reason="Grund für den Bann",
        delete_days="Anzahl der Tage, für die Nachrichten gelöscht werden sollen (0-7)"
    )
    @require_perm("ban")
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "Kein Grund angegeben",
        delete_days: int = 0
    ):
        await interaction.response.defer(ephemeral=True)

        # Hardlock Check
        allowed, block_reason = hardlock_check(interaction, user)
        if not allowed:
            logger.warning(hardlock_log_line(interaction, user, block_reason))
            await interaction.followup.send(
                f"❌ {block_reason}",
                ephemeral=True
            )
            return
        # Cleanup Messages
        delete_days = max(0, min(delete_days, 7))

        #--- Action Helpers ---
        ok, error = await safe_ban(
            interaction.guild,
            user,
            reason=reason,
            delete_message_seconds=delete_days * 86400
        )
        if not ok:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True
            )
            return
        save_ban(interaction.guild.id, user.id, reason)
        # Loggen
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            await log_to_channel(
                self.bot,
                channel_id,
                f"🔨 User gebannt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User:** {user.mention} (ID: {user.id})\n"
                f"**Grund:** {reason}\n",
                discord.Color.dark_red(),
            )
        logger.info(f"BAN | {interaction.user} -> {user} | {reason}")

        await interaction.followup.send(
            f"✅ {user.mention} wurde gebannt. Grund: {reason}",
            ephemeral=True
        )
    @app_commands.command(name="unban", description="Entbannt einen User")
    @app_commands.describe(
        user_id="ID des Users, der entbannt werden soll",
        reason="Grund für den Unban"
    )
    @require_perm("unban")
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "Kein Grund angegeben"
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            uid = int(user_id)
        except ValueError:
            await interaction.followup.send(
                "❌ Ungültige User-ID.",
                ephemeral=True
            )
            return
        user = discord.Object(id=uid)
        #--- Action Helpers ---
        ok, error = await safe_unban(
            interaction.guild, user, reason=reason
        )
        if not ok:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True
            )
            return
        clear_ban(interaction.guild.id, user.id)
        logger.warning(f"CLEAR_BAN CALLED for {user.id}")
        # Loggen
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            await log_to_channel(
                self.bot,
                channel_id,
                f"🔨 User entbannt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User-ID:** {uid}\n"
                f"**Grund:** {reason}\n",
                discord.Color.green(),
            )
        logger.info(f"UNBAN | {interaction.user} -> {uid} | {reason}")
        await interaction.followup.send(
            f"✅ User mit ID `{uid}` wurde entbannt. Grund: {reason}",
            ephemeral=True
        )
    @app_commands.command(name="userinfo", description="Zeigt Informationen an")
    @app_commands.describe(
        user="User, über den Informationen angezeigt werden sollen"
    )
    @require_perm("userinfo")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        #basic info embed
        account_created = discord.utils.format_dt(user.created_at, style="F")
        joined_at = discord.utils.format_dt(user.joined_at, style="F") if user.joined_at else "Unbekannt"
        #warnings count
        total_warnings = count_warnings(
            guild_id=interaction.guild.id,
            user_id=user.id
        )
        last_action = get_last_auto_action(
            guild_id=interaction.guild.id,
            user_id=user.id
        ) or "Keine"
        #timeout info
        is_timed_out = user.is_timed_out()
        timeout_until = (discord.utils.format_dt(user.timed_out_until, style="F") 
                         if is_timed_out else "-"
        )
        
        embed = discord.Embed(
            title=f"ℹ️ Userinfo: {user}",
            color=discord.Color.blue(),
            timestamp=utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="User-ID", value=str(user.id), inline=False)
        embed.add_field(name="Account erstellt am", value=account_created, inline=False)
        embed.add_field(name="Server beigetreten am", value=joined_at, inline=False)
        
        embed.add_field(name="Moderation", 
                        value=(
                        f"**Letzte Auto-Aktion:** {last_action}\n"
                        f"**Verwarnungen:** {total_warnings}\n"
                        f"**Aktiver Timeout:** {'Ja' if is_timed_out else 'Nein'}\n"),
                    inline=False)
        
        if is_timed_out:
            embed.add_field(name="Timeout bis", value=timeout_until, inline=False)

        embed.add_field(name="Top-Rolle", value=user.top_role.mention if user.top_role else "—", inline=False)
        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(name="clear", description="Löscht Nachrichten in einem Kanal")
    @app_commands.describe(
        amount="Anzahl der zu löschenden Nachrichten (1 - 100)"
    )
    @require_perm("clear")
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: int
    ):
        await interaction.response.defer(ephemeral=True)

        if amount < 1 or amount > 100:
            await interaction.followup.send(
                "❌ Die Anzahl muss zwischen 1 und 100 liegen.",
                ephemeral=True
            )
            return
        channel = interaction.channel
        # Sicherstellen, dass der Kanal Textkanal ist
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.followup.send(
                "❌ Dieser Befehl kann nur in Textkanälen verwendet werden.",
                ephemeral=True
            )
            return
        
        #Bot-Objekt sauber ermitteln
        bot_me = interaction.guild.me or interaction.guild.get_member(self.bot.user.id)
        if not bot_me:
            await interaction.followup.send(
                "❌ Bot-Status im Server konnte nicht ermittelt werden.",
                ephemeral=True
                )
            return
        # BOT-Rechte prüfen
        if not channel.permissions_for(bot_me).manage_messages:
            await interaction.followup.send(
                "❌ Mir fehlen die Rechte, Nachrichten zu löschen.",
                ephemeral=True
            )
            return

         # Nachrichten löschen  
        try:
            deleted = await channel.purge(limit=amount + 1) # +1 um die Befehlsnachricht einzuschließen
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Ich habe keine Berechtigung, Nachrichten zu löschen.",
                ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Beim Löschen der Nachrichten ist ein Fehler aufgetreten.",
                ephemeral=True
            )
            return
        deleted_count = max(len(deleted) - 1, 0)

        #Modlog
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id != 0:
            await log_to_channel(
                self.bot,
                channel_id,
                f"🧹 Nachrichten gelöscht",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**Kanal:** {channel.mention} (ID: {channel.id})\n"
                f"**Anzahl:** {deleted_count}\n",
                discord.Color.orange(),
            )
            logger.info(f"CLEAR | {interaction.user} | Channel #{channel.name} ({channel.id}) | {deleted_count} msgs")
        await interaction.followup.send(
            f"✅ {deleted_count} Nachrichten wurden gelöscht.",
            ephemeral=True
        )
async def setup(bot: commands.Bot):    
    await bot.add_cog(Moderation(bot))
    




