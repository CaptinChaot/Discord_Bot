# utils/tickets/manager.py

import re
import discord
from datetime import datetime

from utils.config import config
from utils.logger import log_to_channel
from utils.permissions import get_user_perm_level, PermLevel
from utils.tickets.constants import TICKET_TYPES


def _is_support_plus(member: discord.Member) -> bool:
    return get_user_perm_level(member) >= PermLevel.SUPPORT


def _support_role_ids() -> list[int]:
    # SUP+ Rollen aus deiner config
    keys = ["supporter", "moderator", "admin", "dev", "co_owner", "owner"]
    ids: list[int] = []
    for k in keys:
        rid = config.roles.get(k)
        if rid:
            ids.append(int(rid))
    return ids


def parse_topic(topic: str | None) -> dict:
    """
    Erwartet: OPEN | User:123 | Type:support | ClaimedBy:456
    oder: ARCHIVED | User:123 | Type:support | ClosedBy:456 | ClaimedBy:789
    """
    t = topic or ""
    out = {"user_id": None, "type": None, "claimed_by": None, "closed_by": None, "state": None}

    if t.startswith("OPEN"):
        out["state"] = "OPEN"
    elif t.startswith("ARCHIVED"):
        out["state"] = "ARCHIVED"

    m = re.search(r"User:(\d+)", t)
    if m:
        out["user_id"] = int(m.group(1))

    m = re.search(r"Type:([a-zA-Z0-9_]+)", t)
    if m:
        out["type"] = m.group(1)

    m = re.search(r"ClaimedBy:(\d+)", t)
    if m:
        out["claimed_by"] = int(m.group(1))

    m = re.search(r"ClosedBy:(\d+)", t)
    if m:
        out["closed_by"] = int(m.group(1))

    return out


async def create_ticket_channel(
    *,
    bot: discord.Client,
    guild: discord.Guild,
    user: discord.Member,
    ticket_type: str,
    description: str,
) -> discord.TextChannel:
    category_id = config.tickets.get("category_open")
    category = guild.get_channel(int(category_id)) if category_id else None
    if category is None:
        raise RuntimeError("tickets.category_open fehlt/ungültig")

    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
    }

    # SUP+ Rollen rein
    for rid in _support_role_ids():
        role = guild.get_role(rid)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

    # Bot rein
    me = guild.me or guild.get_member(bot.user.id)
    if me:
        overwrites[me] = discord.PermissionOverwrite(
            view_channel=True,
            manage_channels=True,
            manage_messages=True,
            read_message_history=True
        )

    prefix = config.tickets.get("channel_prefix", "ticket")
    channel_name = f"{prefix}-{ticket_type}-{user.name}".lower()[:90]
    topic = f"OPEN | User:{user.id} | Type:{ticket_type}"

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=topic,
        reason="Ticket created"
    )

    label = TICKET_TYPES.get(ticket_type, {"label": ticket_type})["label"]

    embed = discord.Embed(
        title="🎫 Neues Ticket",
        description=(
            f"**Typ:** {label}\n"
            f"**User:** {user.mention}\n\n"
            f"**Beschreibung:**\n{description}"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="ChaosBot Ticketsystem")

    await channel.send(content=user.mention, embed=embed)

    # Log: Ticket erstellt
    await log_to_channel(
        bot=bot,
        channel_id=int(config.log_channels["moderation"]),
        title="🎫 Ticket erstellt",
        description=(
            f"**Channel:** {channel.mention}\n"
            f"**User:** {user} ({user.id})\n"
            f"**Typ:** {ticket_type}\n"
        ),
    )

    return channel


async def claim_ticket(
    *,
    bot: discord.Client,
    channel: discord.TextChannel,
    claimer: discord.Member,
) -> None:
    if not _is_support_plus(claimer):
        raise PermissionError("SUPPORT+ required")

    info = parse_topic(channel.topic)
    if info["state"] != "OPEN":
        raise RuntimeError("Ticket ist nicht offen")

    if info["claimed_by"] is not None:
        raise RuntimeError("Ticket ist bereits geclaimed")

    new_topic = (channel.topic or "OPEN") + f" | ClaimedBy:{claimer.id}"
    await channel.edit(topic=new_topic, reason="Ticket claimed")

    await log_to_channel(
        bot=bot,
        channel_id=int(config.log_channels["moderation"]),
        title="🖐 Ticket geclaimed",
        description=(
            f"**Channel:** {channel.mention}\n"
            f"**Claimed by:** {claimer} ({claimer.id})\n"
        ),
    )


async def archive_ticket(
    *,
    bot: discord.Client,
    channel: discord.TextChannel,
    closed_by: discord.Member,
) -> None:
    if not _is_support_plus(closed_by):
        raise PermissionError("SUPPORT+ required")

    guild = channel.guild
    info = parse_topic(channel.topic)

    if info["state"] == "ARCHIVED":
        raise RuntimeError("Ticket ist bereits archiviert")

    archive_category_id = config.tickets.get("category_archive")
    archive_category = guild.get_channel(int(archive_category_id)) if archive_category_id else None
    if archive_category is None:
        raise RuntimeError("tickets.category_archive fehlt/ungültig")

    ticket_user = guild.get_member(info["user_id"]) if info["user_id"] else None

    overwrites = channel.overwrites

    # User ausblenden (dein Wunsch)
    hide_from_user = bool(config.tickets.get("archive", {}).get("hide_from_user", True))
    if hide_from_user and ticket_user:
        overwrites[ticket_user] = discord.PermissionOverwrite(view_channel=False)

    # Topic finalisieren (Type beibehalten, ClaimedBy wenn vorhanden)
    t_type = info["type"] or "unknown"
    claimed = f" | ClaimedBy:{info['claimed_by']}" if info["claimed_by"] else ""
    new_topic = f"ARCHIVED | User:{info['user_id']} | Type:{t_type} | ClosedBy:{closed_by.id}{claimed}"

    await channel.edit(
        category=archive_category,
        overwrites=overwrites,
        topic=new_topic,
        reason="Ticket archived"
    )

    await log_to_channel(
        bot=bot,
        channel_id=int(config.log_channels["moderation"]),
        title="🗂 Ticket archiviert",
        description=(
            f"**Channel:** {channel.mention}\n"
            f"**User:** {ticket_user} ({info['user_id']})\n"
            f"**Archiviert von:** {closed_by} ({closed_by.id})\n"
        ),
        color=discord.Color.orange()
    )
