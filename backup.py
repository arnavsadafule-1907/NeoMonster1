import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
from formatter import BotEmbed
from checks import admin_only

BACKUP_DIR = "./data/backups"  # relative path (works on Railway)

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs(BACKUP_DIR, exist_ok=True)

    @app_commands.command(name="backup", description="Create a full server backup (roles, channels, permissions)")
    @admin_only()
    async def backup_create(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        backup_data = {
            "guild_id": guild.id,
            "name": guild.name,
            "owner_id": guild.owner_id,
            "created_at": datetime.utcnow().isoformat(),
            "roles": [],
            "categories": [],
            "channels": []
        }

        # ---- Backup Roles (save ID for mapping) ----
        for role in reversed(guild.roles):
            if role.is_default() or role.managed:
                continue
            backup_data["roles"].append({
                "id": role.id,                     # store old ID for mapping
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "position": role.position,
                "permissions": role.permissions.value
            })

        # ---- Backup Categories ----
        for category in guild.categories:
            backup_data["categories"].append({
                "id": category.id,                 # store old ID for mapping
                "name": category.name,
                "position": category.position,
                "overwrites": self._serialise_overwrites(category)
            })

        # ---- Backup Other Channels (text, voice, stage) ----
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
            backup_data["channels"].append({
                "id": channel.id,                  # store old ID for mapping (optional)
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
                "category_id": channel.category.id if channel.category else None,  # store old category ID
                "overwrites": self._serialise_overwrites(channel)
            })

        filename = f"{BACKUP_DIR}/{guild.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)

        embed = BotEmbed.success("✅ Backup Created", f"Server backup saved to `{filename}`")
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

        report = []

        # ---- Step 1: Delete existing channels and roles ----
        for channel in guild.channels:
            try:
                await channel.delete()
            except Exception as e:
                report.append(f"⚠️ Could not delete channel {channel.name}: {e}")

        for role in guild.roles:
            if role.is_default() or role.managed:
                continue
            try:
                await role.delete()
            except Exception as e:
                report.append(f"⚠️ Could not delete role {role.name}: {e}")

        # ---- Step 2: Create roles and build mapping (old_id -> new_role) ----
        role_mapping = {}  # old_role_id -> new_role_object
        sorted_roles = sorted(backup_data["roles"], key=lambda r: r["position"])

        for role_data in sorted_roles:
            try:
                new_role = await guild.create_role(
                    name=role_data["name"],
                    color=discord.Color(role_data["color"]),
                    hoist=role_data["hoist"],
                    mentionable=role_data["mentionable"],
                    permissions=discord.Permissions(role_data["permissions"]),
                    reason="Server restore"
                )
                role_mapping[role_data["id"]] = new_role
                report.append(f"✅ Role created: {new_role.name}")
            except Exception as e:
                report.append(f"❌ Failed to create role {role_data['name']}: {e}")

        # ---- Step 3: Create categories ----
        category_mapping = {}  # old_category_id -> new_category_object
        for cat_data in backup_data.get("categories", []):
            try:
                new_cat = await guild.create_category(
                    name=cat_data["name"],
                    position=cat_data["position"],
                    reason="Server restore"
                )
                category_mapping[cat_data["id"]] = new_cat
                await self._apply_overwrites(new_cat, cat_data["overwrites"], guild, role_mapping)
                report.append(f"✅ Category created: {new_cat.name}")
            except Exception as e:
                report.append(f"❌ Failed to create category {cat_data['name']}: {e}")

        # ---- Step 4: Create channels ----
        for ch_data in backup_data.get("channels", []):
            try:
                # Find category object using old category_id mapping
                cat_obj = None
                if ch_data.get("category_id"):
                    cat_obj = category_mapping.get(ch_data["category_id"])

                if ch_data["type"] == "text":
                    new_channel = await guild.create_text_channel(
                        name=ch_data["name"],
                        category=cat_obj,
                        position=ch_data["position"],
                        reason="Server restore"
                    )
                elif ch_data["type"] == "voice":
                    new_channel = await guild.create_voice_channel(
                        name=ch_data["name"],
                        category=cat_obj,
                        position=ch_data["position"],
                        reason="Server restore"
                    )
                elif ch_data["type"] == "stage":
                    new_channel = await guild.create_stage_channel(
                        name=ch_data["name"],
                        category=cat_obj,
                        position=ch_data["position"],
                        reason="Server restore"
                    )
                else:
                    report.append(f"⚠️ Skipped channel {ch_data['name']} (unsupported type: {ch_data['type']})")
                    continue

                await self._apply_overwrites(new_channel, ch_data["overwrites"], guild, role_mapping)
                report.append(f"✅ Channel created: {new_channel.name}")
            except Exception as e:
                report.append(f"❌ Failed to create channel {ch_data['name']}: {e}")

        # ---- Step 5: Reorder roles to match original hierarchy ----
        for role_data in sorted_roles:
            new_role = role_mapping.get(role_data["id"])
            if new_role:
                try:
                    await new_role.edit(position=role_data["position"], reason="Server restore")
                except Exception as e:
                    report.append(f"⚠️ Could not set position for {new_role.name}: {e}")

        # ---- Step 6: Send completion report ----
        report_text = "\n".join(report[:20])
        if len(report) > 20:
            report_text += f"\n...and {len(report)-20} more entries."

        embed = BotEmbed.success(
            "✅ Restoration Complete",
            f"**Roles:** {len(role_mapping)} restored\n"
            f"**Categories:** {len(category_mapping)} restored\n"
            f"**Channels:** {len(backup_data['channels'])} restored\n\n"
            f"**Details:**\n{report_text}"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- Helpers ----------
    def _serialise_overwrites(self, channel):
        overwrites = []
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                overwrites.append({
                    "type": "role",
                    "id": target.id,           # store ID for mapping
                    "name": target.name,
                    "allow": overwrite.pair()[0].value,
                    "deny": overwrite.pair()[1].value
                })
            elif isinstance(target, discord.Member):
                overwrites.append({
                    "type": "member",
                    "id": target.id,
                    "name": target.display_name,
                    "allow": overwrite.pair()[0].value,
                    "deny": overwrite.pair()[1].value
                })
        return overwrites

    async def _apply_overwrites(self, channel, overwrites_data, guild, role_mapping):
        for ow in overwrites_data:
            try:
                if ow["type"] == "role":
                    role = role_mapping.get(ow["id"])
                    if not role:
                        # fallback: try by name
                        role = discord.utils.get(guild.roles, name=ow.get("name"))
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
            except Exception:
                pass  # we already report failures at the channel level

async def setup(bot):
    await bot.add_cog(Backup(bot))