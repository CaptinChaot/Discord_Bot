import discord
from datetime import timedelta
from discord.utils import utcnow

from utils.permissions import get_user_perm_level, PermLevel
from utils.logger import logger, log_to_channel
from utils.warnings_db import get_last_auto_action, set_last_auto_action
from utils.config import config


def can_auto_action(interaction: discord.Interaction, user: discord.Member) -> bool:
    if not interaction.guild:
        logger.error("AUTO ACTION BLOCKED | Keine Gilde im Interaction-Objekt")
        return False
    # Bots nie automatisch bestrafen
    if user.bot:
        return False

    # Dev / Owner niemals automatisch bestrafen
    if get_user_perm_level(user) >= PermLevel.DEV:
        logger.info(f"AUTO ACTION SKIPPED | {user} ist Dev/Owner")
        return False
    
    bot_member = interaction.guild.me
    if not bot_member:
        logger.error("AUTO ACTION BLOCKED | Bot-Mitglied nicht gefunden")
        return False

    # Bot-Rolle zu niedrig
    if user.top_role >= bot_member.top_role:
        logger.warning(
            f"AUTO ACTION BLOCKED | Bot-Rolle zu niedrig "
            f"(user={user.top_role.position}, bot={bot_member.top_role.position})"
        )
        return False

    return True

    
async def handle_auto_actions(*,
    bot: discord.Client,
    interaction: discord.Interaction,
    user: discord.Member,
    total_warnings: int,
    timeout_warn: int,
    kick_warn: int,
    ban_warn: int,
    timeout_duration: int
) -> bool:
    """führt auto-Aktion aus
    Rückgabe: True -> Aktion durchgeführt (Ban/Kick/Timeout)
    False -> keine Aktion durchgeführt
    """
    last_action = get_last_auto_action(
        guild_id=interaction.guild.id,
        user_id=user.id
    )

    channel_id = int(config.log_channels.get("moderation", 0))

    # 🔨 BAN
    if total_warnings >= ban_warn and last_action != "ban":
        try:
            await user.ban(
                reason="Automatischer Bann durch Verwarnungen",
                delete_message_days=0
            )
        except discord.Forbidden:
            logger.error(f"AUTO BAN FAILED | Keine Berechtigung zum Bann | {user}")
            return False
        
        if channel_id:
            await log_to_channel(
                bot,
                channel_id,
                "🔨 AUTO BANN",
                f"**User:** {user} ({user.id})\n"
                f"**Warns:** {total_warnings}",
                discord.Color.dark_red()
            )
        set_last_auto_action(interaction.guild.id, user.id, "ban")
        logger.info(f"AUTO BANN | {user}")
        return True

    # 👢 KICK
    if total_warnings >= kick_warn and last_action not in ("kick", "ban"):
        try:
            await user.kick(reason="Automatischer Kick durch Verwarnungen")
        except discord.Forbidden:
            logger.error(f"AUTO KICK FAILED | Keine Berechtigung zum Kick | {user}")
            return False
        
        if channel_id:
            await log_to_channel(
                bot,
                channel_id,
                "👢 AUTO KICK",
                f"**User:** {user} ({user.id})\n"
                f"**Warns:** {total_warnings}",
                discord.Color.orange()
            )
        set_last_auto_action(interaction.guild.id, user.id, "kick")    
        logger.info(f"AUTO KICK | {user}")
        return True

    # ⏱️ TIMEOUT
    if total_warnings >= timeout_warn and last_action not in ("timeout", "kick", "ban"):
        until = utcnow() + timedelta(seconds=timeout_duration)
        try:
            await user.timeout(until, reason="Automatischer Timeout durch Verwarnungen")
        except discord.Forbidden:
            logger.error(f"AUTO TIMEOUT FAILED | Keine Berechtigung zum Timeout | {user}")
            return False
        
        if channel_id:
            await log_to_channel(
                bot,
                channel_id,
                "⏱️ AUTO TIMEOUT",
                f"**User:** {user} ({user.id})\n"
                f"**Dauer:** {timeout_duration}s",
                discord.Color.gold()
            )
        set_last_auto_action(interaction.guild.id, user.id, "timeout")    
        logger.info(f"AUTO TIMEOUT | {user}")
        return True
    return False
