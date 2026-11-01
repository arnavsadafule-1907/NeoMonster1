import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio
import requests
import io
from datetime import datetime
from formatter import BotEmbed

# 🛑 HARDCODED AUTHORIZED ID (Only ff5star can use this)
AUTHORIZED_ID = 912925691639635978


def is_authorized():
    """Custom check to ensure ONLY ff5star can use these commands."""
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id != AUTHORIZED_ID:
            await interaction.response.send_message(
                "❌ **Access Denied.** This command is strictly for the bot owner (ff5star).",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)


class GlobalBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vault_channel_id = os.getenv("GLOBAL_VAULT_CHANNEL_ID") or os.getenv("BACKUP_CHANNEL_ID")

    # ============================================================
    #  HELPER: Fetch all global backups from Discord channel
    # ============================================================
    async def get_global_backups(self):
        if not self.vault_channel_id:
            return []
            
        channel = self.bot.get_channel(int(self.vault_channel_id))
        if not channel:
            return []

        backups = []
        async for msg in channel.history(limit=100):
            if msg.content.startswith("🌐 **GLOBAL BACKUP**") and msg.attachments:
                for att in msg.attachments:
                    if att.filename.endswith(".json"):
                        name = att.filename.replace(".json", "")
                        if "`" in msg.content:
                            name = msg.content.split("`")[1]
                        
                        backups.append({
                            "name": name,
                            "url": att.url,
                            "message_id": msg.id,
                            "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        })
        return backups

    # ============================================================
    #  COMMAND GROUP: /networkbackup
    # ============================================================
    network_group = app_commands.Group(name="networkbackup", description="Manage backups that work across all servers (Owner Only)")

    # ---------- 1. CREATE BACKUP ----------
    @network_group.command(name="create", description="Save this server's layout to the global network vault")
    @app_commands.describe(name="A unique name for this backup (e.g., 'SwordSmp_Main')")
    @is_authorized()
    async def create_backup(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        existing = await self.get_global_backups()
        for b in existing:
            if b["name"].lower() == name.lower():
                return await interaction.followup.send(
                    embed=BotEmbed.error("Name Taken", f"A backup named `{name}` already exists. Please choose a different name."),
                    ephemeral=True
                )

        backup_data = {
            "name": guild.name,
            "created_at": datetime.utcnow().isoformat(),
            "roles": [],
            "categories": [],
            "channels": []
        }

        for role in reversed(guild.roles):
            if role.is_default() or role.managed:
                continue
            backup_data["roles"].append({
                "id": role.id, "name": role.name, "color": role.color.value,
                "hoist": role.hoist, "mentionable": role.mentionable,
                "position": role.position, "permissions": role.permissions.value
            })

        for category in guild.categories:
            backup_data["categories"].append({
                "id": category.id, "name": category.name,
                "position": category.position, "overwrites": self._serialise_overwrites(category)
            })

        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
            backup_data["channels"].append({
                "id": channel.id, "name": channel.name, "type": str(channel.type),
                "position": channel.position,
                "category_id": channel.category.id if channel.category else None,
                "overwrites": self._serialise_overwrites(channel)
            })

        json_string = json.dumps(backup_data, indent=2)
        file = discord.File(fp=io.BytesIO(json_string.encode('utf-8')), filename=f"{name}.json")

        if not self.vault_channel_id:
            return await interaction.followup.send("❌ `BACKUP_CHANNEL_ID` is not set in Render.", ephemeral=True)
            
        vault_channel = self.bot.get_channel(int(self.vault_channel_id))
        if not vault_channel:
            return await interaction.followup.send("❌ Could not find the backup channel.", ephemeral=True)

        await vault_channel.send(
            content=f"🌐 **GLOBAL BACKUP** - `{name}`\n*Created by ff5star on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*",
            file=file
        )

        embed = BotEmbed.success(
            "✅ Global Backup Saved", 
            f"Server layout saved as `{name}`.\nYou can now restore this in **any server**."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- 2. LIST BACKUPS ----------
    @network_group.command(name="list", description="List all saved global backups")
    @is_authorized()
    async def list_backups(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        backups = await self.get_global_backups()

        if not backups:
            return await interaction.followup.send(
                embed=BotEmbed.info("No Backups", "You haven't saved any global backups yet."),
                ephemeral=True
            )

        embed = discord.Embed(title="🌐 Global Network Backups", color=0x3B82F6)
        for b in backups:
            embed.add_field(name=f"📁 {b['name']}", value=f"**Created:** {b['created_at']}", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- 3. RESTORE BACKUP ----------
    @network_group.command(name="restore", description="Wipe this server and load a global backup into it")
    @app_commands.describe(name="The exact name of the backup you want to load")
    @is_authorized()
    async def restore_backup(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        
        backups = await self.get_global_backups()
        target_backup = next((b for b in backups if b["name"].lower() == name.lower()), None)

        if not target_backup:
            return await interaction.followup.send(
                embed=BotEmbed.error("Backup Not Found", f"Could not find `{name}`. Use `/networkbackup list`."),
                ephemeral=True
            )

        try:
            resp = requests.get(target_backup["url"], timeout=15)
            backup_data = resp.json()
        except Exception as e:
            return await interaction.followup.send(
                embed=BotEmbed.error("Download Failed", f"Could not download the backup file.\n```{e}```"),
                ephemeral=True
            )

        guild = interaction.guild
        
        # Inform the user via ephemeral message
        await interaction.followup.send(
            "🔄 **Restoration Started...**\nBecause this deletes all channels, I will send the final report to your DMs. This will take several minutes.", 
            ephemeral=True
        )
        
        try:
            # --- STEP 1: DELETE EVERYTHING ---
            for channel in guild.channels:
                try:
                    await channel.delete()
                    await asyncio.sleep(2)  # 🛑 2 second delay (Prevent Ban)
                except discord.HTTPException:
                    pass

            for role in guild.roles:
                if role.is_default() or role.managed:
                    continue
                try:
                    await role.delete()
                    await asyncio.sleep(2)  # 🛑 2 second delay (Prevent Ban)
                except discord.HTTPException:
                    pass

            # --- STEP 2: CREATE ROLES ---
            role_mapping = {}
            sorted_roles = sorted(backup_data["roles"], key=lambda r: r["position"])
            for role_data in sorted_roles:
                try:
                    new_role = await guild.create_role(
                        name=role_data["name"], color=discord.Color(role_data["color"]),
                        hoist=role_data["hoist"], mentionable=role_data["mentionable"],
                        permissions=discord.Permissions(role_data["permissions"]), reason="Global Restore"
                    )
                    role_mapping[role_data["id"]] = new_role
                    await asyncio.sleep(2)  # 🛑 2 second delay (Prevent Ban)
                except discord.HTTPException:
                    pass

            # --- STEP 3: CREATE CATEGORIES ---
            category_mapping = {}
            for cat_data in backup_data.get("categories", []):
                try:
                    new_cat = await guild.create_category(name=cat_data["name"], position=cat_data["position"], reason="Global Restore")
                    category_mapping[cat_data["id"]] = new_cat
                    await self._apply_overwrites(new_cat, cat_data["overwrites"], guild, role_mapping)
                    await asyncio.sleep(2)  # 🛑 2 second delay (Prevent Ban)
                except discord.HTTPException:
                    pass

            # --- STEP 4: CREATE CHANNELS ---
            for ch_data in backup_data.get("channels", []):
                try:
                    cat_obj = category_mapping.get(ch_data["category_id"]) if ch_data.get("category_id") else None
                    
                    if ch_data["type"] == "text":
                        new_ch = await guild.create_text_channel(name=ch_data["name"], category=cat_obj, position=ch_data["position"], reason="Global Restore")
                    elif ch_data["type"] == "voice":
                        new_ch = await guild.create_voice_channel(name=ch_data["name"], category=cat_obj, position=ch_data["position"], reason="Global Restore")
                    elif ch_data["type"] == "stage":
                        new_ch = await guild.create_stage_channel(name=ch_data["name"], category=cat_obj, position=ch_data["position"], reason="Global Restore")
                    else:
                        continue
                    
                    await self._apply_overwrites(new_ch, ch_data["overwrites"], guild, role_mapping)
                    await asyncio.sleep(2)  # 🛑 2 second delay (Prevent Ban)
                except discord.HTTPException:
                    pass

            # --- STEP 5: REORDER ROLES ---
            for role_data in sorted_roles:
                new_role = role_mapping.get(role_data["id"])
                if new_role:
                    try:
                        await new_role.edit(position=role_data["position"])
                        await asyncio.sleep(1) # 🛑 1 second delay
                    except discord.HTTPException:
                        pass

            embed = BotEmbed.success(
                "✅ Restoration Complete",
                f"Server successfully overwritten with the `{name}` backup.\n\n"
                f"**Roles Restored:** {len(role_mapping)}\n"
                f"**Channels Restored:** {len(backup_data['channels'])}"
            )
            
            # Send to DM to avoid the deleted channel error
            try:
                await interaction.user.send(embed=embed)
            except:
                pass

        except Exception as e:
            try:
                await interaction.user.send(f"❌ **Restore Failed:** {e}")
            except:
                pass

    # ---------- 4. DELETE BACKUP ----------
    @network_group.command(name="delete", description="Delete a global backup permanently")
    @app_commands.describe(name="The exact name of the backup to delete")
    @is_authorized()
    async def delete_backup(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        backups = await self.get_global_backups()
        target_backup = next((b for b in backups if b["name"].lower() == name.lower()), None)

        if not target_backup:
            return await interaction.followup.send(embed=BotEmbed.error("Not Found", f"Could not find `{name}`."), ephemeral=True)

        try:
            channel = self.bot.get_channel(int(self.vault_channel_id))
            msg = await channel.fetch_message(target_backup["message_id"])
            await msg.delete()
            await interaction.followup.send(embed=BotEmbed.success("Deleted", f"Backup `{name}` has been permanently deleted."), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(embed=BotEmbed.error("Error", f"Could not delete the message: {e}"), ephemeral=True)

    # ============================================================
    #  HELPERS
    # ============================================================
    def _serialise_overwrites(self, channel):
        overwrites = []
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                overwrites.append({"type": "role", "id": target.id, "name": target.name, "allow": overwrite.pair()[0].value, "deny": overwrite.pair()[1].value})
            elif isinstance(target, discord.Member):
                overwrites.append({"type": "member", "id": target.id, "name": target.display_name, "allow": overwrite.pair()[0].value, "deny": overwrite.pair()[1].value})
        return overwrites

    async def _apply_overwrites(self, channel, overwrites_data, guild, role_mapping):
        for ow in overwrites_data:
            try:
                if ow["type"] == "role":
                    role = role_mapping.get(ow["id"]) or discord.utils.get(guild.roles, name=ow.get("name"))
                    if role:
                        await channel.set_permissions(role, overwrite=discord.PermissionOverwrite(allow=discord.Permissions(ow["allow"]), deny=discord.Permissions(ow["deny"])))
                        await asyncio.sleep(0.5) # 🛑 Safe delay for permissions
                elif ow["type"] == "member":
                    member = guild.get_member(ow["id"])
                    if member:
                        await channel.set_permissions(member, overwrite=discord.PermissionOverwrite(allow=discord.Permissions(ow["allow"]), deny=discord.Permissions(ow["deny"])))
                        await asyncio.sleep(0.5) # 🛑 Safe delay for permissions
            except discord.HTTPException:
                pass


async def setup(bot):
    await bot.add_cog(GlobalBackup(bot))