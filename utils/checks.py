from utils.config import config
import discord


def has_mod_permissions(interaction: discord.Interaction) -> bool:
    admin_role = int(config.roles.get("admin", 0))
    mod_role = int(config.roles.get("moderator", 0))

    allowed_roles = {admin_role, mod_role}
    user_roles = {role.id for role in interaction.user.roles}

    return not allowed_roles.isdisjoint(user_roles)
