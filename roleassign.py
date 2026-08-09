import discord
from discord import app_commands
from discord.ext import commands
from checks import is_extra_owner
from formatter import BotEmbed

class RoleAssign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="assign", description="Assign a role to a member (nuke, admin, staff, or ticket)")
    @app_commands.describe(member="Member to assign the role to", role="Which role to give")
    @app_commands.choices(role=[
        app_commands.Choice(name="nuke.exe", value="nuke.exe"),
        app_commands.Choice(name="admin.exe", value="admin.exe"),
        app_commands.Choice(name="Staff.exe", value="Staff.exe"),
        app_commands.Choice(name="TicketSupporter", value="TicketSupporter"),
    ])
    async def assign_role(self, interaction: discord.Interaction, member: discord.Member, role: str):
        # Only bot owner, server owner, or extra owners can use this
        if interaction.user.id not in interaction.client.owner_ids and \
           interaction.user.id != interaction.guild.owner_id and \
           not await is_extra_owner(interaction.guild_id, interaction.user.id):
            embed = BotEmbed.error("Permission Denied", "Only the server owner, extra owners, or the bot owner can use this command.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Check if the target role exists
        target_role = discord.utils.get(interaction.guild.roles, name=role)
        if not target_role:
            embed = BotEmbed.error("Role Not Found", f"The `{role}` role does not exist. Use `/setup {role.lower().replace('.exe','')}` to create it first.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Prevent assigning the role if the member already has it
        if target_role in member.roles:
            embed = BotEmbed.warning("Already Has Role", f"{member.mention} already has the {target_role.mention} role.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Assign the role
        try:
            await member.add_roles(target_role, reason=f"Role assigned by {interaction.user}")
            embed = BotEmbed.success("Role Assigned", f"Gave {member.mention} the {target_role.mention} role.")
            await interaction.response.send_message(embed=embed, ephemeral=False)
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I don't have permission to assign that role. Make sure my role is above it and I have `Manage Roles`.")
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RoleAssign(bot))