import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
from formatter import BotEmbed
from checks import admin_only

BACKUP_DIR = "/data/backups"

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs(BACKUP_DIR, exist_ok=True)

    @app_commands.command(name="backup", description="Create a backup of the server")
    @admin_only()
    async def backup_create(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        backup_data = {
            "name": guild.name,
            "owner_id": guild.owner_id,
            "created_at": str(datetime.utcnow()),
            "roles": [],
            "channels": []
        }

        # Backup roles (excluding @everyone and bot roles)
        for role in reversed(guild.roles):
            if role.is_default():
                continue
            backup_data["roles"].append({
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "position": role.position,
                "permissions": role.permissions.value
            })

        # Backup channels with permissions
        for channel in guild.channels:
            channel_data = {
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
                "category_id": channel.category_id,
                "overwrites": []
            }
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Role):
                    channel_data["overwrites"].append({
                        "type": "role",
                        "id": target.id,
                        "allow": overwrite.pair()[0].value,
                        "deny": overwrite.pair()[1].value
                    })
                elif isinstance(target, discord.Member):
                    channel_data["overwrites"].append({
                        "type": "member",
                        "id": target.id,
                        "allow": overwrite.pair()[0].value,
                        "deny": overwrite.pair()[1].value
                    })
            backup_data["channels"].append(channel_data)

        filename = f"{BACKUP_DIR}/{guild.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)

        embed = BotEmbed.success("Backup Created", f"Server state saved to `{filename}`")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="restore", description="Restore server from the latest backup (DESTRUCTIVE)")
    @app_commands.describe(confirm="Type 'CONFIRM' to proceed")
    @admin_only()
    async def restore_backup(self, interaction: discord.Interaction, confirm: str):
        if confirm != "CONFIRM":
            embed = BotEmbed.error("Confirmation Required", "Type `CONFIRM` to proceed with restoration.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # Find latest backup for this guild
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith(str(guild.id))], reverse=True)
        if not backups:
            embed = BotEmbed.error("No Backup", "No backup found for this server.")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        with open(f"{BACKUP_DIR}/{backups[0]}", "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        # Delete existing channels and roles
        for channel in guild.channels:
            try:
                await channel.delete()
            except:
                pass
        for role in guild.roles:
            if role.is_default() or role.managed:
                continue
            try:
                await role.delete()
            except:
                pass

        # Restore roles
        created_roles = {}
        for role_data in backup_data["roles"]:
            try:
                role = await guild.create_role(
                    name=role_data["name"],
                    color=discord.Color(role_data["color"]),
                    hoist=role_data["hoist"],
                    mentionable=role_data["mentionable"],
                    permissions=discord.Permissions(role_data["permissions"]),
                    reason="Server restore"
                )
                created_roles[role.name] = role
            except:
                pass

        # Restore channels
        for channel_data in backup_data["channels"]:
            try:
                if channel_data["type"] == "text":
                    channel = await guild.create_text_channel(
                        name=channel_data["name"],
                        category=discord.utils.get(guild.categories, id=channel_data["category_id"]),
                        position=channel_data["position"]
                    )
                elif channel_data["type"] == "voice":
                    channel = await guild.create_voice_channel(
                        name=channel_data["name"],
                        category=discord.utils.get(guild.categories, id=channel_data["category_id"]),
                        position=channel_data["position"]
                    )
                # Apply permissions
                for overwrite in channel_data["overwrites"]:
                    if overwrite["type"] == "role":
                        role = discord.utils.get(guild.roles, id=overwrite["id"])
                        if role:
                            await channel.set_permissions(role, overwrite=discord.PermissionOverwrite(
                                allow=discord.Permissions(overwrite["allow"]),
                                deny=discord.Permissions(overwrite["deny"])
                            ))
            except:
                pass

        embed = BotEmbed.success("Restoration Complete", "Server has been restored from backup.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Backup(bot))