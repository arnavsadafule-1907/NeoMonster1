from discord import app_commands
import discord

NUKE_ROLE = "nuke.exe"
ADMIN_ROLE = "admin.exe"
STAFF_ROLE = "Staff.exe"              # new lower staff role
TICKET_SUPPORTER_ROLE = "TicketSupporter"  # new ticket-specific role

def nuke_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if role and role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(NUKE_ROLE)
    return app_commands.check(predicate)

def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE)
        nuke_role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if admin_role and admin_role in interaction.user.roles:
            return True
        if nuke_role and nuke_role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(f"{ADMIN_ROLE} or {NUKE_ROLE}")
    return app_commands.check(predicate)

def staff_only():
    """Allows Staff.exe, admin.exe, nuke.exe, and server owner."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
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

def ticket_staff_only():
    """Allows TicketSupporter, Staff.exe, admin.exe, nuke.exe, and server owner."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
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