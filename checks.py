from discord import app_commands
import discord

NUKE_ROLE = "nuke.exe"
ADMIN_ROLE = "admin.exe"

def nuke_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        # 1) Bot owner always bypasses
        if interaction.user.id in interaction.client.owner_ids:
            return True
        # 2) Server owner always bypasses
        if interaction.user.id == interaction.guild.owner_id:
            return True
        # 3) Must have the nuke.exe role
        role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if role and role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(NUKE_ROLE)
    return app_commands.check(predicate)

def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        # 1) Bot owner always bypasses
        if interaction.user.id in interaction.client.owner_ids:
            return True
        # 2) Server owner always bypasses
        if interaction.user.id == interaction.guild.owner_id:
            return True
        # 3) Check for admin.exe OR nuke.exe
        admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE)
        nuke_role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if admin_role and admin_role in interaction.user.roles:
            return True
        if nuke_role and nuke_role in interaction.user.roles:
            return True
        raise app_commands.MissingRole(f"{ADMIN_ROLE} or {NUKE_ROLE}")
    return app_commands.check(predicate)