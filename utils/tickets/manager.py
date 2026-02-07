# utils/tickets/manager.py

import discord
from utils.config import config
from utils.permissions import get_user_perm_level, PermLevel
from utils.logger import log_to_channel
from utils.tickets.constants import TICKET_TYPES


def _is_support_plus(member: discord.Member) -> bool:
    return get_user_perm_level(member) >= PermLevel.SUPPORT


def _get_ticket_cfg() -> dict:
    if not hasattr(config, "tickets"):
        raise RuntimeError("tickets-Block fehlt in config.yaml")
    return config.tickets


async def create_ticket_channel(
    *,
    bot: discord.Client,
    guild: discord.Guild,
    user: discord.Member,
    ticket_type: str,
    description: str,
):
    tickets_cfg = _get_ticket_cfg()

    category_id = tickets_cfg.get("category_open")
    if not category_id:
        raise RuntimeError("tickets.category_open fehlt")

    category = guild.get_channel(int(category_id))
    if not category:
        raise RuntimeError("Ticket-OPEN-Kategorie nicht gefunden")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
    }

    # SUPPORT+ Rollen sehen Tickets (Kategorie kann auch privat sein)
    for role_name in ["supporter", "moderator", "admin", "dev", "co_owner", "owner"]:
        role_id = config.roles.get(role_name)
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

    # Bot selbst
    bot_member = guild.me or guild.get_member(bot.user.id)
    overwrites[bot_member] = discord.PermissionOverwrite(
        view_channel=True,
        manage_channels=True,
        manage_messages=True,
        read_message_history=True,
    )

    prefix = tickets_cfg.get("channel_preffix", "ticket").lower()
    channel_name = f"{prefix}-{ticket_type}-{user.name}".lower()[:90]
    topic = f"OPEN | User:{user.id} | Type:{ticket_type}"

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=topic,
        reason="Ticket created",
    )

    label = TICKET_TYPES.get(ticket_type, {}).get("label", ticket_type)

    embed = discord.Embed(
        title="🎫 Neues Ticket",
        description=(
            f"**Typ:** {label}\n"
            f"**User:** {user.mention}\n\n"
            f"**Beschreibung:**\n{description}"
        ),
        color=discord.Color.blurple(),
    )

    await channel.send(content=user.mention, embed=embed)

    await log_to_channel(
        bot=bot,
        channel_id=config.log_channels["moderation"],
        title="🎫 Ticket erstellt",
        description=(
            f"**Channel:** {channel.mention}\n"
            f"**User:** {user} ({user.id})\n"
            f"**Typ:** {ticket_type}"
        ),
    )

    return channel


async def archive_ticket(
    *,
    bot: discord.Client,
    channel: discord.TextChannel,
    closed_by: discord.Member,
):
    if not _is_support_plus(closed_by):
        raise PermissionError("SUPPORT+ erforderlich")

    tickets_cfg = _get_ticket_cfg()

    category_id = tickets_cfg.get("category_closed")
    if not category_id:
        raise RuntimeError("tickets.category_closed fehlt")

    archive_category = channel.guild.get_channel(int(category_id))
    if not archive_category:
        raise RuntimeError("Ticket-ARCHIV-Kategorie nicht gefunden")

    overwrites = channel.overwrites

    if tickets_cfg.get("archive", {}).get("hide_from_user", True):
        # User aus Topic lesen
        for part in (channel.topic or "").split("|"):
            if "User:" in part:
                uid = int(part.split(":")[1])
                member = channel.guild.get_member(uid)
                if member:
                    overwrites[member] = discord.PermissionOverwrite(view_channel=False)

    await channel.edit(
        category=archive_category,
        overwrites=overwrites,
        topic=f"ARCHIVED | ClosedBy:{closed_by.id}",
        reason="Ticket archived",
    )

    await log_to_channel(
        bot=bot,
        channel_id=config.log_channels["moderation"],
        title="🗂 Ticket archiviert",
        description=(
            f"**Channel:** {channel.mention}\n"
            f"**Archiviert von:** {closed_by} ({closed_by.id})"
        ),
        color=discord.Color.orange(),
    )
