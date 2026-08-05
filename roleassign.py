import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed

class RoleAssign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = os.getenv("DATABASE_PATH", "./data/security.db")

    async def is_whitelisted_or_has_role(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id:
            return True
        admin_role = discord.utils.get(interaction.guild.roles, name="admin.exe")
        nuke_role = discord.utils.get(interaction.guild.roles, name="nuke.exe")
        if admin_role and admin_role in interaction.user.roles:
            return True
        if nuke_role and nuke_role in interaction.user.roles:
            return True
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT 1 FROM whitelist WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, interaction.user.id))
            if await cursor.fetchone():
                return True
            for role in interaction.user.roles:
                cursor = await db.execute("SELECT 1 FROM whitelist WHERE guild_id = ? AND role_id = ?", (interaction.guild_id, role.id))
                if await cursor.fetchone():
                    return True
        return False

    @app_commands.command(name="roleassign", description="Give a member admin.exe or nuke.exe role")
    @app_commands.describe(member="Member to assign role", role="Which role")
    @app_commands.choices(role=[
        app_commands.Choice(name="admin.exe", value="admin.exe"),
        app_commands.Choice(name="nuke.exe", value="nuke.exe")
    ])
    async def roleassign(self, interaction: discord.Interaction, member: discord.Member, role: str):
        if not await self.is_whitelisted_or_has_role(interaction):
            embed = BotEmbed.error("Permission Denied", "You must be whitelisted or have admin.exe/nuke.exe role.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        target_role = discord.utils.get(interaction.guild.roles, name=role)
        if not target_role:
            embed = BotEmbed.error("Role Not Found", f"Role `{role}` doesn't exist. Use `/setup` first.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)
        if target_role in member.roles:
            embed = BotEmbed.warning("Already Has Role", f"{member.mention} already has {role}.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)
        try:
            await member.add_roles(target_role, reason=f"Assigned by {interaction.user}")
            embed = BotEmbed.success("Role Assigned", f"Gave {member.mention} the {role} role.")
        except discord.Forbidden:
            embed = BotEmbed.error("Forbidden", "I lack permission to assign this role.")
        await interaction.response.send_message(embed=embed, ephemeral=False)

async def setup(bot):
    await bot.add_cog(RoleAssign(bot))