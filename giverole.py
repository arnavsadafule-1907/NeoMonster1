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
    @admin_only()
    async def giverole(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role, reason: str | None = None):
        if interaction.guild is None:
            return

        if role.is_default():
            embed = BotEmbed.error("Invalid Role", "The @everyone role cannot be assigned manually.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if role >= interaction.guild.me.top_role:
            embed = BotEmbed.error("Role Too High", "I cannot assign this role because it is above my highest role. Please move my role higher.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if isinstance(interaction.user, discord.Member):
            if role >= interaction.user.top_role and interaction.user != interaction.guild.owner and interaction.user.id not in interaction.client.owner_ids:
                embed = BotEmbed.error("Role Too High", "You cannot assign a role equal to or higher than your own highest role.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        if role in user.roles:
            embed = BotEmbed.warning("Already Assigned", f"{user.mention} already has the {role.mention} role.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

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
