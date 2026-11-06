import os
import aiosqlite
import discord
from discord import app_commands

from db import get_db_path

NUKE_ROLE = "nuke.exe"
ADMIN_ROLE = "admin.exe"
STAFF_ROLE = "Staff.exe"
TICKET_SUPPORTER_ROLE = "TicketSupporter"


async def is_extra_owner(guild_id: int | None, user_id: int) -> bool:
    if not guild_id:
        return False
    async with aiosqlite.connect(get_db_path()) as db:
        cursor = await db.execute(
            "SELECT 1 FROM extra_owners WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        return await cursor.fetchone() is not None


def owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True
        raise app_commands.MissingRole("Server Owner or Bot Owner")
    return app_commands.check(predicate)


def nuke_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True

        user_roles = getattr(interaction.user, "roles", [])
        role = discord.utils.get(interaction.guild.roles, name=NUKE_ROLE)
        if role and role in user_roles:
            return True

        perms = getattr(interaction.user, "guild_permissions", None)
        if perms and perms.administrator:
            return True

        raise app_commands.MissingRole(NUKE_ROLE)
    return app_commands.check(predicate)


def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True

        perms = getattr(interaction.user, "guild_permissions", None)
        if perms and perms.administrator:
            return True

        user_roles = getattr(interaction.user, "roles", [])
        for role_name in [ADMIN_ROLE, NUKE_ROLE]:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in user_roles:
                return True

        raise app_commands.MissingRole(ADMIN_ROLE)
    return app_commands.check(predicate)


def staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True

        perms = getattr(interaction.user, "guild_permissions", None)
        if perms and perms.administrator:
            return True

        user_roles = getattr(interaction.user, "roles", [])
        for role_name in [STAFF_ROLE, ADMIN_ROLE, NUKE_ROLE]:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in user_roles:
                return True

        raise app_commands.MissingRole(STAFF_ROLE)
    return app_commands.check(predicate)


def ticket_staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True

        perms = getattr(interaction.user, "guild_permissions", None)
        if perms and perms.administrator:
            return True

        user_roles = getattr(interaction.user, "roles", [])
        for role_name in [TICKET_SUPPORTER_ROLE, STAFF_ROLE, ADMIN_ROLE, NUKE_ROLE]:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in user_roles:
                return True

        raise app_commands.MissingRole(TICKET_SUPPORTER_ROLE)
    return app_commands.check(predicate)
