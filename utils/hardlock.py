# utils/hardlock.py
from __future__ import annotations

import discord
from typing import Tuple, Optional


def hardlock_check(
    interaction: discord.Interaction,
    target: discord.Member,
    *,
    allow_self: bool = False,
    allow_owner_bypass: bool = True,
) -> Tuple[bool, str]:
    """
    Zentraler Hardlock:
    - blockt Selbst-Moderation
    - blockt Aktionen gegen den Bot
    - prüft Bot-Rollenhierarchie (kann der Bot den Target moderieren?)
    - prüft Invoker-Rollenhierarchie (darf der User den Target moderieren?)
    - optional: Owner-BYPASS für Rollen-Checks

    Returns:
        (allowed: bool, reason: str)
    """

    guild = interaction.guild
    if guild is None:
        return False, "❌ Dieser Befehl funktioniert nur auf einem Server."

    invoker = interaction.user
    if not isinstance(invoker, discord.Member):
        invoker = guild.get_member(interaction.user.id)  # fallback
        if invoker is None:
            return False, "❌ Konnte deine Member-Daten nicht laden."

    # --- Baseline Blocks ---
    if not allow_self and target.id == invoker.id:
        return False, "❌ Du kannst dich nicht selbst moderieren."

    me = guild.me or guild.get_member(guild._state.user.id)  # bot as member
    if me is None:
        return False, "❌ Bot-Status im Server konnte nicht ermittelt werden."

    if target.id == me.id:
        return False, "❌ Ich kann mich nicht selbst moderieren."

    # --- Owner Bypass (optional) ---
    is_owner = (invoker.id == guild.owner_id)
    if is_owner and allow_owner_bypass:
        # Owner darf über Hierarchie hinweg, Bot muss aber trotzdem können.
        if target.top_role >= me.top_role:
            return False, "❌ Meine Rolle ist zu niedrig, um diese Person zu moderieren."
        return True, ""

    # --- Bot can act? ---
    # discord.py: Member.top_role ist höchster Role-Objekt im Server
    if target.top_role >= me.top_role:
        return False, "❌ Meine Rolle ist zu niedrig, um diese Person zu moderieren."

    # --- Invoker can act? ---
    # Wenn invoker <= target und invoker nicht owner -> block
    if invoker.top_role <= target.top_role:
        return False, "❌ Zielrolle ist gleich oder höher als deine."

    return True, ""


def hardlock_log_line(
    interaction: discord.Interaction,
    target: discord.Member,
    reason: str,
) -> str:
    """Optional: einheitlicher Log-String."""
    guild = interaction.guild
    invoker = interaction.user
    g = f"{guild.name} ({guild.id})" if guild else "DM/UnknownGuild"
    return f"HARDLOCK BLOCK | {g} | {invoker} ({invoker.id}) -> {target} ({target.id}) | {reason}"
