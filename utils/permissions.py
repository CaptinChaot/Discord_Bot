import discord
from enum import IntEnum
from utils.config import config
from .permissions import PermLevel


class PermLevel(IntEnum):
    MEMBER = 0
    SUPPORT = 5
    MOD = 10
    ADMIN = 20
    DEV = 30
    CO_OWNER = 35
    OWNER = 40

ROLE_TO_LEVEL = {
    role_id: level
    for role_id, level in {
    #MEMBER ROLES
    config.roles.get("member_1"): PermLevel.MEMBER,
    config.roles.get("member_2"): PermLevel.MEMBER,
    config.roles.get("member_3"): PermLevel.MEMBER,
    config.roles.get("member_4"): PermLevel.MEMBER,

    #Staff ROLES
    config.roles.get("supporter"): PermLevel.SUPPORT,
    config.roles.get("moderator"): PermLevel.MOD,
    config.roles.get("admin"): PermLevel.ADMIN,
    config.roles.get("dev"): PermLevel.DEV,
    config.roles.get("owner"): PermLevel.OWNER,
    config.roles.get("co_owner"): PermLevel.OWNER,
} .items()
    if role_id is not None
}


def get_user_perm_level(member: discord.Member) -> PermLevel:
    # Safety-Fallback: Discord-Admin = Owner-Level
    if member.guild_permissions.administrator:
        return PermLevel.OWNER # Admin-Notfall-Fallback

    highest = PermLevel.MEMBER

    for role in member.roles:
        level = ROLE_TO_LEVEL.get(role.id)
        if level and level > highest:
            highest = level

    return highest

