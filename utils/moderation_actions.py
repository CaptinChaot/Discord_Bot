import discord
from datetime import timedelta
from discord.utils import utcnow
from utils.config import config

async def safe_timeout(
    member: discord.Member,
    duration_seconds: int,
    *,
    reason: str
) -> tuple[bool, str]:
    """
    Führt einen Timeout sicher aus.
    Returns:
        (success, error_message)
    """
    if duration_seconds <= 0:
        return False, "Ungültige Timeout-Dauer."

    try:
        until = utcnow() + timedelta(seconds=duration_seconds)
        await member.timeout(until, reason=reason)
        return True, ""
    except discord.Forbidden:
        return False, "Discord hat den Timeout blockiert (keine Rechte)."
    except Exception:
        return False, "Unerwarteter Fehler beim Setzen des Timeouts."


async def safe_untimeout(
    member: discord.Member,
    *,
    reason: str
) -> tuple[bool, str]:
    """
    Entfernt einen Timeout sicher.
    """
    if member.timed_out_until is None:
        return False, "User ist aktuell nicht im Timeout."

    try:
        await member.timeout(None, reason=reason)
        return True, ""
    except discord.Forbidden:
        return False, "Discord hat das Entfernen blockiert (keine Rechte)."
    except Exception:
        return False, "Unerwarteter Fehler beim Entfernen des Timeouts."

async def safe_kick(
    member: discord.Member,
    *,
    reason: str
) -> tuple[bool, str]:
    """
    Führt einen Kick sicher aus.
    Returns:
        (success, error_message)
    """
    try:
        await member.kick(reason=reason)
        return True, ""
    except discord.Forbidden:
        return False, "Discord hat den Kick blockiert (keine Rechte)."
    except Exception:
        return False, "Unerwarteter Fehler beim Kicken des Users."
    
async def safe_ban(
    guild: discord.Guild,
    target: discord.abc.Snowflake,
    *,
    reason: str,
    delete_message_seconds: int = 0
) -> tuple[bool, str]:
    """
    Führt einen Ban sicher aus.
    Returns:
        (success, error_message)
    """
    try:
        await guild.ban(target, reason=reason, delete_message_seconds=delete_message_seconds)
        return True, ""
    except discord.Forbidden:
        return False, "Discord hat den Ban blockiert (keine Rechte)."
    except Exception:
        return False, "Unerwarteter Fehler beim Bannen des Users."
    
async def safe_unban(
    guild: discord.Guild,
    target: discord.abc.Snowflake,
    *,
    reason: str
) -> tuple[bool, str]:
    """
    Entfernt einen Ban sicher.
    Returns:
        (success, error_message)
    """
    try:
        await guild.unban(target, reason=reason)
        return True, ""
    except discord.Forbidden:
        return False, "Discord hat das Unbannen blockiert (keine Rechte)."
    except Exception:
        return False, "Unerwarteter Fehler beim Unbannen des Users."

def get_auto_action_preview(warn_count: int) -> str | None:
    mod_cfg = config.moderation

    timeout_at = mod_cfg.get("warn_timeout_threshold")
    ban_at = mod_cfg.get("warn_ban_threshold")

    # Schon Bann-Level erreicht
    if ban_at is not None and warn_count >= ban_at:
        return None

    # Nächste Aktion: Bann
    if timeout_at is not None and warn_count >= timeout_at:
        remaining = ban_at - warn_count if ban_at else None
        if remaining is not None:
            return f"Bann (bei {remaining} weiterer Verwarnung{'en' if remaining != 1 else ''})"
        return "Bann"

    # Nächste Aktion: Timeout
    if timeout_at is not None:
        remaining = timeout_at - warn_count
        return f"Timeout (bei {remaining} weiterer Verwarnung{'en' if remaining != 1 else ''})"

    return None
