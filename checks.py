from discord import app_commands
import discord
import aiosqlite
import os

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

NUKE_ROLE = "nuke.exe"
ADMIN_ROLE = "admin.exe"
STAFF_ROLE = "Staff.exe"
TICKET_SUPPORTER_ROLE = "TicketSupporter"

# ================================================================
#  HELPER: check if a user is an extra owner for a guild
# ================================================================
async def is_extra_owner(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM extra_owners WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        return await cursor.fetchone() is not None

# ================================================================
#  ROLE CHECKS
# ================================================================

# ---------- New: Owner only ----------
def owner_only():
    """Restrict command to server owner, bot owners, and extra owners only."""
    async def predicate(interaction: discord.Interaction) -> bool:
        # 1) Bot owner (from .env)
        if interaction.user.id in interaction.client.owner_ids:
            return True
        # 2) Server owner
        if interaction.user.id == interaction.guild.owner_id:
            return True
        # 3) Extra owner (stored in DB)
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True
        raise app_commands.MissingRole("Server Owner or Bot Owner")
    return app_commands.check(predicate)

# ---------- Nuke only ----------
def nuke_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True
        role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if role and role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(NUKE_ROLE)
    return app_commands.check(predicate)

# ---------- Admin only ----------
def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True
        admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE)
        nuke_role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if admin_role and admin_role in interaction.user.roles:
            return True
        if nuke_role and nuke_role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(f"{ADMIN_ROLE} or {NUKE_ROLE}")
    return app_commands.check(predicate)

# ---------- Staff only ----------
def staff_only():
    """Allows Staff.exe, admin.exe, nuke.exe, server owner, bot owners, and extra owners."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE)
        admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE)
        nuke_role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if staff_role and staff_role in interaction.user.roles:
            return True
        if admin_role and admin_role in interaction.user.roles:
            return True
        if nuke_role and nuke_role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(f"{STAFF_ROLE}, {ADMIN_ROLE}, or {NUKE_ROLE}")
    return app_commands.check(predicate)

# ---------- Ticket staff only ----------
def ticket_staff_only():
    """Allows TicketSupporter, Staff.exe, admin.exe, nuke.exe, server owner, bot owners, and extra owners."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True
        ticket_role = discord.utils.get(interaction.guild.roles, name=TICKET_SUPPORTER_ROLE)
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE)
        admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE)
        nuke_role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if ticket_role and ticket_role in interaction.user.roles:
            return True
        if staff_role and staff_role in interaction.user.roles:
            return True
        if admin_role and admin_role in interaction.user.roles:
            return True
        if nuke_role and nuke_role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(f"{TICKET_SUPPORTER_ROLE}, {STAFF_ROLE}, {ADMIN_ROLE}, or {NUKE_ROLE}")
    return app_commands.check(predicate)