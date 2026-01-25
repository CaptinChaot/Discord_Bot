import discord
from utils.permissions import get_user_perm_level, PermLevel


def has_perm(interaction: discord.Interaction, level: PermLevel) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    return get_user_perm_level(interaction.user) >= level


def can_warn(interaction: discord.Interaction) -> bool:
    return has_perm(interaction, PermLevel.MOD)


def can_timeout(interaction: discord.Interaction) -> bool:
    return has_perm(interaction, PermLevel.MOD)


def can_kick(interaction: discord.Interaction) -> bool:
    return has_perm(interaction, PermLevel.ADMIN)


def can_ban(interaction: discord.Interaction) -> bool:
    return has_perm(interaction, PermLevel.ADMIN)


def can_dev(interaction: discord.Interaction) -> bool:
    return has_perm(interaction, PermLevel.DEV)

def can_userinfo(interaction: discord.Interaction) -> bool:
    return has_perm(interaction, PermLevel.MOD)

def can_clear(interaction: discord.Interaction) -> bool:
    return has_perm(interaction, PermLevel.MOD)