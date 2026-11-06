import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed


class RemoveRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="removerole", description="Remove any role from a member")
    @app_commands.describe(
        user="The member to remove the role from",
        role="The role to remove",
        reason="Reason for the removal (optional)"
    )
    @admin_only()
    async def removerole(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role, reason: str | None = None):
        if interaction.guild is None:
            return

        if role.is_default():
            embed = BotEmbed.error("Invalid Role", "The @everyone role cannot be removed manually.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if role >= interaction.guild.me.top_role:
            embed = BotEmbed.error("Role Too High", "I cannot remove this role because it is above my highest role.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if isinstance(interaction.user, discord.Member):
            if role >= interaction.user.top_role and interaction.user != interaction.guild.owner and interaction.user.id not in interaction.client.owner_ids:
                embed = BotEmbed.error("Role Too High", "You cannot remove a role equal to or higher than your own highest role.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        if role not in user.roles:
            embed = BotEmbed.warning("Not Assigned", f"{user.mention} does not have the {role.mention} role.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            await user.remove_roles(role, reason=f"Role removed by {interaction.user} ({reason or 'No reason provided'})")
            embed = BotEmbed.success("Role Removed", f"Successfully removed {role.mention} from {user.mention}.\n**Reason:** {reason or 'No reason provided'}")
            await interaction.response.send_message(embed=embed, ephemeral=False)
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Error", "I do not have permission to remove this role.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = BotEmbed.error("Unexpected Error", f"An unexpected error occurred: {e}")
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(RemoveRole(bot))
