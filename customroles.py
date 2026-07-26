import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class CustomRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_roles = {}

    @app_commands.command(name="customrole", description="Create or manage your custom role")
    @app_commands.describe(action="Create or delete", name="Role name (for create)", color="Hex color (e.g., #ff0000)")
    @app_commands.choices(action=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="delete", value="delete"),
        app_commands.Choice(name="list", value="list"),
    ])
    @admin_only()
    async def customrole(self, interaction: discord.Interaction, action: str, name: str = None, color: str = None):
        if action == "create":
            if not name:
                embed = BotEmbed.error("Missing Name", "You must provide a name.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            try:
                col = discord.Color.from_str(color) if color else discord.Color.random()
            except:
                col = discord.Color.random()
            role = await interaction.guild.create_role(name=name, color=col, reason="Custom role")
            await role.edit(position=interaction.guild.me.top_role.position - 1)
            await interaction.user.add_roles(role)
            self.user_roles.setdefault(interaction.user.id, []).append(role.id)
            embed = BotEmbed.success("Role Created", f"Role {role.mention} has been created and assigned to you.")
        elif action == "delete":
            role_ids = self.user_roles.get(interaction.user.id, [])
            if not role_ids:
                embed = BotEmbed.error("No Roles", "You have no custom roles to delete.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            role = interaction.guild.get_role(role_ids[0])
            if role:
                await role.delete(reason="Custom role delete")
                role_ids.remove(role.id)
                embed = BotEmbed.success("Role Deleted", f"Role {role.name} deleted.")
            else:
                embed = BotEmbed.error("Not Found", "Role not found (may already be deleted).")
        elif action == "list":
            role_ids = self.user_roles.get(interaction.user.id, [])
            roles = [interaction.guild.get_role(rid) for rid in role_ids if interaction.guild.get_role(rid)]
            if not roles:
                embed = BotEmbed.info("Your Roles", "You have no custom roles.")
            else:
                embed = BotEmbed.info("Your Roles", "\n".join([r.mention for r in roles]))
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CustomRoles(bot))