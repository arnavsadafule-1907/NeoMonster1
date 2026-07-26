import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class AdminSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Create the admin.exe and nuke.exe roles")
    @app_commands.describe(role_type="Which role to create")
    @app_commands.choices(role_type=[
        app_commands.Choice(name="admin.exe", value="admin"),
        app_commands.Choice(name="nuke.exe", value="nuke")
    ])
    @admin_only()
    async def setup(self, interaction: discord.Interaction, role_type: str):
        await interaction.response.defer(ephemeral=False)

        role_name = f"{role_type}.exe"
        existing = discord.utils.get(interaction.guild.roles, name=role_name)
        if existing:
            await interaction.followup.send(
                embed=BotEmbed.info("Already Exists", f"Role {existing.mention} already exists."),
                ephemeral=False
            )
            return

        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.followup.send(
                embed=BotEmbed.error("Missing Permission", "I need the **Manage Roles** permission."),
                ephemeral=True
            )
            return

        try:
            if role_type == "admin":
                # Admin role – has all moderation perms EXCEPT Manage Roles
                # This prevents manual role assignment; use /roleassign instead
                perms = discord.Permissions(
                    kick_members=True,
                    ban_members=True,
                    manage_messages=True,
                    manage_channels=True,
                    manage_webhooks=True,
                    moderate_members=True,
                    view_audit_log=True,
                    read_messages=True,
                    send_messages=True,
                    connect=True,
                    speak=True,
                    use_voice_activation=True
                    # manage_roles=False  (explicitly left out)
                )
                colour = discord.Color.blue()
            else:  # nuke.exe
                perms = discord.Permissions(administrator=True)
                colour = discord.Color.red()

            role = await interaction.guild.create_role(
                name=role_name,
                permissions=perms,
                colour=colour,
                reason="Setup via NeoMonster"
            )
            # Place the new role just below the bot's top role
            try:
                await role.edit(position=interaction.guild.me.top_role.position - 1)
            except:
                pass

            await interaction.followup.send(
                embed=BotEmbed.success("Role Created", f"{role.mention} created with default permissions."),
                ephemeral=False
            )

        except discord.Forbidden:
            await interaction.followup.send(
                embed=BotEmbed.error("Forbidden", "I lack permission to create roles. Move my role higher."),
                ephemeral=False
            )
        except Exception as e:
            await interaction.followup.send(
                embed=BotEmbed.error("Error", str(e)),
                ephemeral=False
            )


async def setup(bot):
    await bot.add_cog(AdminSetup(bot))