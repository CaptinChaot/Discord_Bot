import discord

from datetime import timedelta
from discord import app_commands, Interaction
from discord.ext import commands
from utils.config import config
from utils.logger import logger, log_to_channel
from discord.utils import utcnow
from utils.checks import has_mod_permissions
from utils.warnings_db import (
    add_warning,
    count_warnings,
    delete_warnings as db_delete_warnings,
    delete_warning_by_id, get_last_warning_id,
    get_last_auto_action, set_last_auto_action,
)


mod_cfg = config.moderation

timeout_warn = mod_cfg.get("warn_timeout_threshold", 2)
timeout_duration = mod_cfg.get("warn_timeout_duration", 300)
kick_warn = mod_cfg.get("warn_kick_threshold", 3)
ban_warn = mod_cfg.get("warn_ban_threshold", 5)



class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @app_commands.command(name="timeout", description="Setze einen User in Timeout")
    async def timeout(self, interaction: Interaction, user: discord.Member, duration: int, reason: str = "Kein Grund angegeben"):
        await interaction.response.defer(ephemeral=True)
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
        "❌ Du hast keine Berechtigung, diesen Befehl zu nutzen.",
        ephemeral=True
    )
            return
        if duration <= 0:
            await interaction.followup.send(
                "❌ Dauer muss größer als 0 sein.",
            ephemeral=True
    )
            return


        until = utcnow() + timedelta(seconds=duration)
        await user.timeout(until, reason=reason)
        channel_id = int(config.log_channels.get("moderation", 0)) # 0 = kein Logging - durch config.yaml wird geguckt obs nen log_channel gibt
        if channel_id != 0:
            await log_to_channel(
                 self.bot,
                channel_id,
                f"⏱️ Timeout gesetzt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})"
                f"**User:** {user.mention} (ID: {user.id})\n"
                f"**Dauer:** {duration} Sekunden\n"
                f"**Grund:** {reason}\n",
                discord.Color.red(),
                )
        logger.info(
    f"TIMEOUT | {interaction.user} -> {user} | {duration}s | {reason}"
        )

        await interaction.followup.send(
            f"✅ {user.mention} wurde für {duration} Sekunden in Timeout gesetzt. Grund: {reason}",
            ephemeral=True
        )

    @app_commands.command(name="untimeout", description="Entferne den Timeout von einem User")
    async def untimeout(self, interaction: Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
        "❌ Du hast keine Berechtigung, diesen Befehl zu nutzen.",
        ephemeral=True
    )
            return

        await user.timeout(None, reason="Timeout entfernt durch Moderation")
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id != 0:
                await log_to_channel(
                    self.bot,
                    channel_id,
                    f"⏱️ Timeout entfernt",
                    f"**Moderator:** {interaction.user} (ID: {interaction.user.id})"
                    f"**User:** {user.mention} (ID: {user.id})\n",
                    discord.Color.green(),
                )
        logger.info(f"UNTIMEOUT | {interaction.user} -> {user}")
        await interaction.followup.send(
            f"✅ Timeout von {user.mention} wurde entfernt.",
            ephemeral=True
        )

    @app_commands.command(name="warn",description="Verwarnt einen User und loggt es im Modlog")
    @app_commands.describe(
        user="User, der verwarnt werden soll",
        reason="Grund für die Verwarnung"
    )
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return

        # Selbstschutz
        if user == interaction.user:
            await interaction.followup.send(
                "❌ Du kannst dich nicht selbst verwarnen.",
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
        can_auto_action = True

        # Bots nicht automatisch bestrafen
        if user.bot:
            can_auto_action = False
        # Bot-Mitglied sauber holen (kein deprecated me)
        bot_member = interaction.guild.get_member(self.bot.user.id) or interaction.guild.me
        if not bot_member:
            can_auto_action = False
        elif user.top_role >= bot_member.top_role:
            logger.warning(
                f"AUTO ACTION BLOCKED | Bot-Rolle zu niedrig für {user} ({user.id})"
            )
            can_auto_action = False
        # User noch im Server?
        if not interaction.guild.get_member(user.id):
            can_auto_action = False


        if can_auto_action:
            last_action = get_last_auto_action(
                guild_id=interaction.guild.id,
                user_id=user.id
            )
            if total_warnings >= ban_warn and last_action != "ban":
                try:
                    await user.send(
                        f"🔨 **Du wurdest von {interaction.guild.name} gebannt**\n"
                        f"**Grund:** Automatischer Bann durch Verwarnungen\n"
                        f"**Moderator:** System"
                    )
                except discord.Forbidden:
                    pass

                try:
                    await user.ban(
                        reason="Automatischer Bann durch Verwarnungen",delete_message_days=0
                    )
                except discord.Forbidden:
                    logger.error(
                        f"AUTO BAN FAILED | Keine Rechte zum Bannen von {user} ({user.id})"
                    )
                    
                    return
                except discord.HTTPException:
                    logger.error(
                        f"AUTO BAN FAILED | HTTPException beim Bannen von {user} ({user.id})"
                    )
                    return
                
                channel_id = int(config.log_channels.get("moderation", 0))
                if channel_id != 0:
                    await log_to_channel(
                        self.bot,
                        channel_id,
                        f"🔨 AUTO BANN",
                        f"**User:** {user} (ID: {user.id})\n"
                        f"**Auslöser:** Auto-System\n"
                        f"**Grund:** Automatischer Bann durch Verwarnungen\n"
                        f"**Anzahl der Verwarnungen:** {total_warnings}\n",
                        discord.Color.dark_red(),
                    )
                logger.info(
                    f"AUTO BANN | {user} | {total_warnings} Warns"
                )
                set_last_auto_action(
                    guild_id=interaction.guild.id,
                    user_id=user.id,
                    action="ban"
                )
                return
            
            elif total_warnings >= kick_warn and last_action not in ("kick", "ban"):
                try:
                    await user.send(
                        f"👢 **Du wurdest von {interaction.guild.name} gekickt**\n"
                        f"**Grund:** Automatischer Kick durch Verwarnungen\n"
                        f"**Moderator:** System"
                        )
                except discord.Forbidden:
                    pass
                try:
                    await user.kick(reason="Automatischer Kick durch Verwarnungen")

                except discord.Forbidden:
                    logger.error(
                        f"AUTO KICK FAILED | Keine Rechte zum Kicken von {user} ({user.id})"
                    )
                    return
                except discord.HTTPException:
                    logger.error(
                        f"AUTO KICK FAILED | HTTPException beim Kicken von {user} ({user.id})"
                    )
                    return

                channel_id = int(config.log_channels.get("moderation", 0))
                if channel_id != 0:
                    await log_to_channel(
                        self.bot,
                        channel_id,
                        f"👢 AUTO KICK",
                        f"**User:** {user} (ID: {user.id})\n"
                        f"**Auslöser:** Auto-System\n"
                        f"**Grund:** Automatischer Kick durch Verwarnungen\n"
                        f"**Anzahl der Verwarnungen:** {total_warnings}\n",
                        discord.Color.dark_red(),
                    )
                logger.info(
                    f"AUTO KICK | {user} | {total_warnings} Warns"
                )
                set_last_auto_action(
                    guild_id=interaction.guild.id,
                    user_id=user.id,
                    action="kick"
                )
                return
            
            elif total_warnings >= timeout_warn and last_action is None:
                try:
                    await user.send(
                        f"⏱️ **Du wurdest von {interaction.guild.name} in Timeout gesetzt**\n"
                        f"**Grund:** Automatischer Timeout durch Verwarnungen\n"
                        f"**Moderator:** System"
                    )
                except discord.Forbidden:
                    pass
                
                try:
                    until = utcnow() + timedelta(seconds=timeout_duration)#
                    await user.timeout(
                        until,
                        reason="Automatischer Timeout durch Verwarnungen"
                    )
                except discord.Forbidden:
                    logger.error(
                        f"AUTO TIMEOUT FAILED | Keine Rechte zum Timeout von {user} ({user.id})"
                    )
                    return
                except discord.HTTPException:
                    logger.error(
                        f"AUTO TIMEOUT FAILED | HTTPException beim Timeout von {user} ({user.id})"
                    )
                    
                    return
                
                channel_id = int(config.log_channels.get("moderation", 0))
                if channel_id != 0:
                    await log_to_channel(
                        self.bot,
                        channel_id,
                        f"⏱️ AUTO TIMEOUT",
                        f"**User:** {user} (ID: {user.id})\n"
                        f"**Auslöser:** Auto-System\n"
                        f"**Grund:** Automatischer Timeout durch Verwarnungen\n"
                        f"**Dauer:** {timeout_duration} Sekunden\n"
                        f"**Anzahl der Verwarnungen:** {total_warnings}\n",
                        discord.Color.orange(),
                    )
                logger.info(
                    f"AUTO TIMEOUT | {user} | {total_warnings} Warns"
                )
                set_last_auto_action(
                    guild_id=interaction.guild.id,
                    user_id=user.id,
                    action="timeout"
                )
                return
            
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
        if channel_id != 0:
            try:
                modlog_channel = await self.bot.fetch_channel(channel_id)
                await modlog_channel.send(embed=embed)
            except discord.NotFound:
                logger.error(f"MODLOG | Channel {channel_id} nicht gefunden")
            except discord.Forbidden:
                logger.error(f"MODLOG | Keine Rechte für Channel {channel_id}")
            except Exception as e:
                logger.exception(f"MODLOG | Unbekannter Fehler: {e}")

        await interaction.followup.send(
        f"✅ {user.mention} wurde verwarnt.",
        ephemeral=True
    )

    @app_commands.command(name="warnings", description="Zeigt die Anzahl der Verwarnungen eines Users an")
    @app_commands.describe(
        user="User, dessen Verwarnungen angezeigt werden sollen"
    )  

    async def warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return
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
    async def delete_warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
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
        if channel_id != 0:
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
    async def unwarn(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return
        if user.bot:
            await interaction.followup.send(
                "❌ Bots können keine Verwarnungen haben.",
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
        if channel_id != 0:
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
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "Kein Grund angegeben"
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return

        # Selbstschutz
        if user == interaction.user:
            await interaction.followup.send(
                "❌ Du kannst dich nicht selbst kicken.",
                ephemeral=True
            )
            return
        if user.top_role >= interaction.user.top_role:
            await interaction.followup.send(
                "❌ Du kannst keinen User mit einer gleichen oder höheren Rolle kicken.",
                ephemeral=True
            )
            return
        if user.top_role >= interaction.guild.me.top_role:
            await interaction.followup.send(
                "❌ Ich kann keinen User mit einer gleichen oder höheren Rolle kicken.",
                ephemeral=True
            )
            return
        if user.bot:
            await interaction.followup.send(
                "❌ Bots können nicht gekickt werden.",
                ephemeral=True
            )
            return  
        try:
            await user.send(
                f"👢 **Du wurdest von {interaction.guild.name} gekickt**\n"
                f"**Grund:** {reason}\n"
                f"**Moderator:** {interaction.user}"
            )
        except discord.Forbidden:
            pass  # DMs aus → egal, Kick zählt
        # Kick ausführen
        await user.kick(reason=reason)

        # Loggen
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id != 0:
            await log_to_channel(
                self.bot,
                channel_id,
                f"👢 User gekickt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User:** {user.mention} (ID: {user.id})\n"
                f"**Grund:** {reason}\n",
                discord.Color.red(),
            )
        logger.info(f"KICK | {interaction.user} -> {user} | {reason}")

        await interaction.followup.send(
            f"✅ {user.mention} wurde gekickt. Grund: {reason}",
            ephemeral=True
        )

    @app_commands.command(name="ban", description="Bannt einen User vom Server")
    @app_commands.describe(
        user="User, der gebannt werden soll",
        reason="Grund für den Ban"
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "Kein Grund angegeben"
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return

        # Selbstschutz
        if user == interaction.user:
            await interaction.followup.send(
                "❌ Du kannst dich nicht selbst bannen.",
                ephemeral=True
            )
            return
        if user.top_role >= interaction.user.top_role:
            await interaction.followup.send(
                "❌ Du kannst keinen User mit einer gleichen oder höheren Rolle bannen.",
                ephemeral=True
            )
            return
        if user.top_role >= interaction.guild.me.top_role:
            await interaction.followup.send(
                "❌ Ich kann keinen User mit einer gleichen oder höheren Rolle bannen.",
                ephemeral=True
            )
            return
        if user.id == interaction.guild.owner_id:
            await interaction.followup.send(
                "❌ Du kannst den Serverbesitzer nicht bannen.",
                ephemeral=True
            )
            return
        try:
            await user.send(
                f"🔨 **Du wurdest von {interaction.guild.name} gebannt**\n"
                f"**Grund:** {reason}\n"
                f"**Moderator:** {interaction.user}"
            )
        except discord.Forbidden:
            pass  # DMs aus → egal, Ban zählt
        # Ban ausführen
        try:
            await user.ban(reason=reason, delete_message_days=0)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Ich habe keine Berechtigung, diesen User zu bannen.",
                ephemeral=True
            )
            return    
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Beim Bannen des Users ist ein Fehler aufgetreten.",
                ephemeral=True
            )
            return

        # Loggen
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id != 0:
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
    @app_commands.command(name="unban", description="Entbannt einen User vom Server")
    @app_commands.describe(
        user_id="ID des Users, der entbannt werden soll",
        reason="Grund für den Unban"
    )
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: int,
        reason: str = "Kein Grund angegeben"
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission Check
        if not has_mod_permissions(interaction):
            await interaction.followup.send(
                "❌ Keine Berechtigung.",
                ephemeral=True
            )
            return
        # User holen
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            await interaction.followup.send(
                "❌ User nicht gefunden.",
                ephemeral=True
            )
            return
        # prüfen ob user gebannt ist
        try:
            ban_entry = await interaction.guild.fetch_ban(user)
        except discord.NotFound:
            await interaction.followup.send(
                "❌ Der User ist nicht gebannt.",
                ephemeral=True
            )
            return

        # Unban ausführen
        try:
            await interaction.guild.unban(user, reason=reason)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Ich habe keine Berechtigung, diesen User zu entbannen.",
                ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Beim Entbannen des Users ist ein Fehler aufgetreten.",
                ephemeral=True
            )
            return

        # Loggen
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id != 0:
            await log_to_channel(
                self.bot,
                channel_id,
                f"🔨 User entbannt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User:** {user} (ID: {user.id})\n"
                f"**Grund:** {reason}\n",
                discord.Color.green(),
            )
        logger.info(f"UNBAN | {interaction.user} -> {user} | {reason}")

        await interaction.followup.send(
            f"✅ {user.mention} wurde entbannt. Grund: {reason}",
            ephemeral=True
        )
async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))


