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
            "categories": [],
            "channels": []
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

        # 2) Backup categories
        for category in guild.categories:
            backup_data["categories"].append({
                "name": category.name,
                "position": category.position,
                "overwrites": self._serialise_overwrites(category)
            })

        # 3) Backup other channels
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
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

        embed = BotEmbed.success("Backup Created", f"Backup saved to persistent storage.")
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

        # Find latest backup
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith(str(guild.id))],
            reverse=True
        )
        if not backups:
            embed = BotEmbed.error("No Backup", "No backup found for this server.")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        with open(f"{BACKUP_DIR}/{backups[0]}", "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        report = []  # collect success/failure messages

        # --- Delete existing channels & roles ---
        for channel in guild.channels:
            try:
                await channel.delete()
            except Exception as e:
                report.append(f"❌ Could not delete channel {channel.name}: {e}")
        for role in guild.roles:
            if role.is_default() or role.managed:
                continue
            try:
                await role.delete()
            except Exception as e:
                report.append(f"❌ Could not delete role {role.name}: {e}")

        # --- Recreate roles ---
        role_map = {}
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
                report.append(f"✅ Role created: {role.name}")
            except Exception as e:
                report.append(f"❌ Failed to create role {role_data['name']}: {e}")

        # --- Recreate categories first ---
        category_map = {}
        for cat_data in backup_data.get("categories", []):
            try:
                category = await guild.create_category(
                    name=cat_data["name"],
                    position=cat_data["position"],
                    reason="Server restore"
                )
                await self._apply_overwrites(category, cat_data["overwrites"], guild, role_map)
                category_map[cat_data["name"]] = category
                report.append(f"✅ Category created: {category.name}")
            except Exception as e:
                report.append(f"❌ Failed to create category {cat_data['name']}: {e}")

        # --- Recreate other channels ---
        for ch_data in backup_data.get("channels", []):
            try:
                parent = category_map.get(ch_data.get("category_name"))
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
                    report.append(f"⚠️ Skipped channel {ch_data['name']} (type {ch_data['type']} not supported)")
                    continue

                await self._apply_overwrites(channel, ch_data["overwrites"], guild, role_map)
                report.append(f"✅ Channel created: {channel.name}")
            except Exception as e:
                report.append(f"❌ Failed to create channel {ch_data['name']}: {e}")

        # Send report to the user (truncate if too long)
        report_text = "\n".join(report[:20])  # Discord embed field limit
        if len(report) > 20:
            report_text += f"\n...and {len(report)-20} more entries."

        embed = BotEmbed.success("Restore Complete", report_text or "No changes reported.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- Helpers ----------
    def _serialise_overwrites(self, channel) -> list:
        overwrites = []
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                overwrites.append({
                    "type": "role",
                    "name": target.name,
                    "allow": overwrite.pair()[0].value,
                    "deny": overwrite.pair()[1].value
                })
            elif isinstance(target, discord.Member):
                overwrites.append({
                    "type": "member",
                    "id": target.id,
                    "allow": overwrite.pair()[0].value,
                    "deny": overwrite.pair()[1].value
                })
        return overwrites

    async def _apply_overwrites(self, channel, overwrites_data, guild, role_map):
        for ow in overwrites_data:
            try:
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
            except:
                pass  # we already report failures at the channel level


async def setup(bot):
    await bot.add_cog(Backup(bot))