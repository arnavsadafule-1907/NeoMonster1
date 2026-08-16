import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class GiveRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="giverole", description="Assign any role from this server to a member")
    @app_commands.describe(
        user="The member to receive the role",
        role="The role to assign",
        reason="Reason for the role change (optional)"
    )
    @admin_only()   # ✅ replaces all manual permission checks
    async def giverole(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role, reason: str = None):
        # Prevent assigning @everyone
        if role.is_default():
            embed = BotEmbed.error("Invalid Role", "The @everyone role cannot be assigned manually.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Ensure the bot can assign this role (role below bot's top role)
        if role >= interaction.guild.me.top_role:
            embed = BotEmbed.error("Role Too High", "I cannot assign this role because it is above my highest role. Please move my role higher.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Check if the member already has the role
        if role in user.roles:
            embed = BotEmbed.warning("Already Assigned", f"{user.mention} already has the {role.mention} role.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Attempt to add the role
        try:
            await user.add_roles(role, reason=f"Role assigned by {interaction.user} ({reason or 'No reason provided'})")
            embed = BotEmbed.success("Role Assigned", f"Successfully gave {role.mention} to {user.mention}.\n**Reason:** {reason or 'No reason provided'}")
            await interaction.response.send_message(embed=embed, ephemeral=False)
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Error", "I do not have permission to assign this role. Please check my role hierarchy and permissions.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = BotEmbed.error("Unexpected Error", f"An unexpected error occurred: {e}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GiveRole(bot))