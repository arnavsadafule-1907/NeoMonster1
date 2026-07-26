import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
from formatter import BotEmbed
from checks import admin_only

BACKUP_DIR = "/data/backups"          # Railway persistent volume

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs(BACKUP_DIR, exist_ok=True)

    @app_commands.command(name="backup", description="Create a full server backup")
    @admin_only()
    async def backup_create(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        backup_data = {
            "name": guild.name,
            "owner_id": guild.owner_id,
            "created_at": str(datetime.utcnow()),
            "roles": [],
            "categories": [],      # store categories separately
            "channels": []          # text, voice, etc.
        }

        # 1) Backup roles (skip @everyone)
        for role in guild.roles:
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

        # 2) Backup categories first (they are channels with type "category")
        for category in guild.categories:
            backup_data["categories"].append({
                "name": category.name,
                "position": category.position,
                "overwrites": self._serialise_overwrites(category)
            })

        # 3) Backup other channels (text, voice, etc.)
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue   # already backed up
            backup_data["channels"].append({
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
                "category_name": channel.category.name if channel.category else None,
                "overwrites": self._serialise_overwrites(channel)
            })

        filename = f"{BACKUP_DIR}/{guild.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)

        embed = BotEmbed.success("Backup Created", f"Server state saved.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="restore", description="Restore server from the latest backup (DESTRUCTIVE)")
    @app_commands.describe(confirm="Type 'CONFIRM' to proceed")
    @admin_only()
    async def restore_backup(self, interaction: discord.Interaction, confirm: str):
        if confirm != "CONFIRM":
            embed = BotEmbed.error("Confirmation Required", "Type `CONFIRM` to proceed.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # Find latest backup for this server
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith(str(guild.id))],
            reverse=True
        )
        if not backups:
            embed = BotEmbed.error("No Backup", "No backup found for this server.")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        with open(f"{BACKUP_DIR}/{backups[0]}", "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        # --- Destroy existing channels & roles ---
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

        # --- Recreate roles ---
        role_map = {}   # old_name -> new role object
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
                role_map[role_data["name"]] = role
            except:
                pass

        # --- Recreate categories first ---
        category_map = {}
        for cat_data in backup_data["categories"]:
            try:
                category = await guild.create_category(
                    name=cat_data["name"],
                    position=cat_data["position"],
                    reason="Server restore"
                )
                await self._apply_overwrites(category, cat_data["overwrites"], guild, role_map)
                category_map[cat_data["name"]] = category
            except:
                pass

        # --- Recreate other channels ---
        for ch_data in backup_data["channels"]:
            try:
                # Determine parent category
                parent = category_map.get(ch_data["category_name"])

                if ch_data["type"] == "text":
                    channel = await guild.create_text_channel(
                        name=ch_data["name"],
                        category=parent,
                        position=ch_data["position"],
                        reason="Server restore"
                    )
                elif ch_data["type"] == "voice":
                    channel = await guild.create_voice_channel(
                        name=ch_data["name"],
                        category=parent,
                        position=ch_data["position"],
                        reason="Server restore"
                    )
                else:
                    continue   # skip unsupported types

                await self._apply_overwrites(channel, ch_data["overwrites"], guild, role_map)
            except:
                pass

        embed = BotEmbed.success("Restoration Complete", "Server has been restored from backup.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- Helper methods ----------
    def _serialise_overwrites(self, channel) -> list:
        """Convert channel overwrites to a list of dicts."""
        overwrites = []
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                overwrites.append({
                    "type": "role",
                    "name": target.name,   # store name, not ID (safer across restores)
                    "allow": overwrite.pair()[0].value,
                    "deny": overwrite.pair()[1].value
                })
            elif isinstance(target, discord.Member):
                overwrites.append({
                    "type": "member",
                    "id": target.id,        # members are identified by ID
                    "allow": overwrite.pair()[0].value,
                    "deny": overwrite.pair()[1].value
                })
        return overwrites

    async def _apply_overwrites(self, channel, overwrites_data, guild, role_map):
        """Apply saved overwrites to a channel."""
        for ow in overwrites_data:
            if ow["type"] == "role":
                role = role_map.get(ow["name"])
                if role:
                    await channel.set_permissions(
                        role,
                        overwrite=discord.PermissionOverwrite(
                            allow=discord.Permissions(ow["allow"]),
                            deny=discord.Permissions(ow["deny"])
                        )
                    )
            elif ow["type"] == "member":
                member = guild.get_member(ow["id"])
                if member:
                    await channel.set_permissions(
                        member,
                        overwrite=discord.PermissionOverwrite(
                            allow=discord.Permissions(ow["allow"]),
                            deny=discord.Permissions(ow["deny"])
                        )
                    )


async def setup(bot):
    await bot.add_cog(Backup(bot))