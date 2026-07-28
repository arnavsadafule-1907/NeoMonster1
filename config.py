import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import json
import os
import logging
from checks import admin_only, nuke_only
from formatter import BotEmbed

logger = logging.getLogger("discord.cogs.config")

EVENT_TYPES = [
    "channel_create", "channel_delete",
    "role_create", "role_delete",
    "ban", "kick",
    "webhook_create", "webhook_delete"
]

PUNISHMENT_OPTIONS = ["none", "strip", "kick", "ban"]

class Config(commands.GroupCog, name="antinuke"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = os.getenv("DATABASE_PATH", "./data/security.db")

    async def ensure_guild_entry(self, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
            await db.commit()

    # ---------- Help (open to everyone) ----------
    @app_commands.command(name="help", description="Show the anti‑nuke help menu")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛡️ NeoMonster Anti‑Nuke Help", color=0x3B82F6)
        embed.add_field(name="/antinuke settings", value="View current configuration", inline=False)
        embed.add_field(name="/antinuke toggle", value="Enable/disable the system", inline=False)
        embed.add_field(name="/antinuke module", value="Turn detection modules on/off", inline=False)
        embed.add_field(name="/antinuke threshold", value="Set action limits", inline=False)
        embed.add_field(name="/antinuke timewindow", value="Set rate‑limit window", inline=False)
        embed.add_field(name="/antinuke punishment", value="Choose punishment mode", inline=False)
        embed.add_field(name="/antinuke quarantine-role", value="Set the quarantine role", inline=False)
        embed.add_field(name="/antinuke logchannel", value="Set the alert log channel", inline=False)
        embed.add_field(name="/antinuke emergency", value="Lockdown / kick nuker", inline=False)
        embed.add_field(name="/antinuke whitelist", value="Manage immune users/roles (nuke only)", inline=False)
        embed.set_footer(text="Use /help for the full bot command list")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Toggle (nuke only) ----------
    @app_commands.command(name="toggle", description="Enable or disable the entire anti‑nuke system")
    @app_commands.describe(state="On or Off")
    @app_commands.choices(state=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")])
    @nuke_only()
    async def toggle_antinuke(self, interaction: discord.Interaction, state: str):
        await self.ensure_guild_entry(interaction.guild_id)
        enabled = 1 if state == "on" else 0
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE guild_settings SET antinuke_enabled = ? WHERE guild_id = ?", (enabled, interaction.guild_id))
            await db.commit()
        embed = BotEmbed.success("Anti‑Nuke", f"System {'enabled' if enabled else 'disabled'}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Emergency (nuke only) ----------
    @app_commands.command(name="emergency", description="Emergency lockdown / unlock / kick nuker")
    @app_commands.describe(action="Action to perform", user="User to kick (only for kick_nuker)")
    @app_commands.choices(action=[
        app_commands.Choice(name="lock", value="lock"),
        app_commands.Choice(name="unlock", value="unlock"),
        app_commands.Choice(name="kick_nuker", value="kick_nuker")
    ])
    @nuke_only()
    async def emergency(self, interaction: discord.Interaction, action: str, user: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        if action == "lock":
            everyone = guild.default_role
            count = 0
            for channel in guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                    try:
                        await channel.set_permissions(everyone, send_messages=False, connect=False)
                        count += 1
                    except:
                        pass
            embed = BotEmbed.success("Lockdown", f"Locked {count} channels.")
        elif action == "unlock":
            everyone = guild.default_role
            count = 0
            for channel in guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                    try:
                        await channel.set_permissions(everyone, send_messages=True, connect=True)
                        count += 1
                    except:
                        pass
            embed = BotEmbed.success("Unlocked", f"Unlocked {count} channels.")
        elif action == "kick_nuker":
            if not user:
                embed = BotEmbed.error("Missing User", "Specify a user to kick.")
                return await interaction.followup.send(embed=embed, ephemeral=True)
            try:
                await guild.kick(user, reason="Emergency nuker removal")
                embed = BotEmbed.success("Kicked", f"{user.mention} has been kicked.")
            except Exception as e:
                embed = BotEmbed.error("Error", str(e))
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- Settings (admin only) ----------
    @app_commands.command(name="settings", description="View current anti‑nuke configuration")
    @admin_only()
    async def settings(self, interaction: discord.Interaction):
        await self.ensure_guild_entry(interaction.guild_id)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (interaction.guild_id,))
            row = await cursor.fetchone()
            modules = json.loads(row["modules"])
            thresholds = json.loads(row["thresholds"])
            time_window = row["time_window"]
            punishment = row["punishment"]
            quarantine_role = f"<@&{row['quarantine_role_id']}>" if row["quarantine_role_id"] else "Not set"
            log_channel = f"<#{row['log_channel_id']}>" if row["log_channel_id"] else "Not set"
            enabled = "Enabled" if row["antinuke_enabled"] else "Disabled"

        embed = BotEmbed.info("🛡️ Anti‑Nuke Configuration")
        embed.add_field(name="System Status", value=enabled, inline=False)
        embed.add_field(name="Punishment", value=punishment, inline=True)
        embed.add_field(name="Quarantine Role", value=quarantine_role, inline=True)
        embed.add_field(name="Log Channel", value=log_channel, inline=True)
        modules_text = "\n".join([f"{k}: {'✅' if v else '❌'}" for k, v in modules.items()])
        embed.add_field(name="Modules", value=modules_text, inline=False)
        thresh_text = "\n".join([f"{k}: {v} per {time_window}s" for k, v in thresholds.items()])
        embed.add_field(name="Thresholds", value=thresh_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Module (admin only) ----------
    @app_commands.command(name="module", description="Enable/disable a detection module")
    @app_commands.describe(module="The event type", state="Enable or disable")
    @app_commands.choices(module=[app_commands.Choice(name=e, value=e) for e in EVENT_TYPES])
    @app_commands.choices(state=[app_commands.Choice(name="enable", value="enable"), app_commands.Choice(name="disable", value="disable")])
    @admin_only()
    async def module(self, interaction: discord.Interaction, module: str, state: str):
        await self.ensure_guild_entry(interaction.guild_id)
        new_state = True if state == "enable" else False
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT modules FROM guild_settings WHERE guild_id = ?", (interaction.guild_id,))
            row = await cursor.fetchone()
            modules = json.loads(row["modules"])
            modules[module] = new_state
            await db.execute("UPDATE guild_settings SET modules = ? WHERE guild_id = ?", (json.dumps(modules), interaction.guild_id))
            await db.commit()
        embed = BotEmbed.success("Module Updated", f"`{module}` {'enabled' if new_state else 'disabled'}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Threshold (admin only) ----------
    @app_commands.command(name="threshold", description="Set action threshold for an event")
    @app_commands.describe(module="Event type", count="Max allowed actions")
    @app_commands.choices(module=[app_commands.Choice(name=e, value=e) for e in EVENT_TYPES])
    @admin_only()
    async def threshold(self, interaction: discord.Interaction, module: str, count: int):
        if count < 1:
            return await interaction.response.send_message(embed=BotEmbed.error("Invalid", "Count must be at least 1."), ephemeral=True)
        await self.ensure_guild_entry(interaction.guild_id)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT thresholds FROM guild_settings WHERE guild_id = ?", (interaction.guild_id,))
            row = await cursor.fetchone()
            thresholds = json.loads(row["thresholds"])
            thresholds[module] = count
            await db.execute("UPDATE guild_settings SET thresholds = ? WHERE guild_id = ?", (json.dumps(thresholds), interaction.guild_id))
            await db.commit()
        embed = BotEmbed.success("Threshold Updated", f"`{module}` threshold set to **{count}**.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Time Window (admin only) ----------
    @app_commands.command(name="timewindow", description="Set the detection time window (seconds)")
    @app_commands.describe(seconds="Seconds (5–60)")
    @admin_only()
    async def timewindow(self, interaction: discord.Interaction, seconds: int):
        if seconds < 5 or seconds > 60:
            return await interaction.response.send_message(embed=BotEmbed.error("Invalid", "Time window must be between 5 and 60 seconds."), ephemeral=True)
        await self.ensure_guild_entry(interaction.guild_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE guild_settings SET time_window = ? WHERE guild_id = ?", (seconds, interaction.guild_id))
            await db.commit()
        embed = BotEmbed.success("Time Window Updated", f"Window set to **{seconds}s**.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Punishment (admin only) ----------
    @app_commands.command(name="punishment", description="Set punishment mode for offenders")
    @app_commands.describe(mode="Punishment type")
    @app_commands.choices(mode=[app_commands.Choice(name=m, value=m) for m in PUNISHMENT_OPTIONS])
    @admin_only()
    async def punishment(self, interaction: discord.Interaction, mode: str):
        await self.ensure_guild_entry(interaction.guild_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE guild_settings SET punishment = ? WHERE guild_id = ?", (mode, interaction.guild_id))
            await db.commit()
        embed = BotEmbed.success("Punishment Updated", f"Mode set to **{mode}**.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Quarantine Role (admin only) ----------
    @app_commands.command(name="quarantine-role", description="Set the role given to stripped offenders")
    @app_commands.describe(role="Quarantine role (should have no permissions)")
    @admin_only()
    async def quarantine_role(self, interaction: discord.Interaction, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(embed=BotEmbed.error("Role Too High", "I cannot assign a role higher than my own."), ephemeral=True)
        await self.ensure_guild_entry(interaction.guild_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE guild_settings SET quarantine_role_id = ? WHERE guild_id = ?", (role.id, interaction.guild_id))
            await db.commit()
        embed = BotEmbed.success("Quarantine Role Set", f"Offenders will get {role.mention}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Log Channel (admin only) ----------
    @app_commands.command(name="logchannel", description="Set the anti‑nuke alert channel")
    @app_commands.describe(channel="Text channel for logs")
    @admin_only()
    async def logchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.ensure_guild_entry(interaction.guild_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE guild_settings SET log_channel_id = ? WHERE guild_id = ?", (channel.id, interaction.guild_id))
            await db.commit()
        embed = BotEmbed.success("Log Channel Set", f"Alerts will be sent to {channel.mention}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Whitelist group (nuke only) ----------
    whitelist_group = app_commands.Group(name="whitelist", description="Manage anti‑nuke whitelist")

    @whitelist_group.command(name="add", description="Add a user or role to the whitelist")
    @app_commands.describe(user="User to whitelist", role="Role to whitelist")
    @nuke_only()   # <-- changed from admin_only
    async def whitelist_add(self, interaction: discord.Interaction, user: discord.User = None, role: discord.Role = None):
        if not user and not role:
            return await interaction.response.send_message(embed=BotEmbed.error("Missing Target", "Provide a user or role."), ephemeral=True)
        async with aiosqlite.connect(self.db_path) as db:
            try:
                if user:
                    await db.execute("INSERT INTO whitelist (guild_id, user_id) VALUES (?, ?)", (interaction.guild_id, user.id))
                if role:
                    await db.execute("INSERT INTO whitelist (guild_id, role_id) VALUES (?, ?)", (interaction.guild_id, role.id))
                await db.commit()
            except aiosqlite.IntegrityError:
                return await interaction.response.send_message(embed=BotEmbed.warning("Already Whitelisted", "That user/role is already whitelisted."), ephemeral=True)
        embed = BotEmbed.success("Whitelisted", f"Added to the whitelist.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @whitelist_group.command(name="remove", description="Remove from whitelist")
    @app_commands.describe(user="User to remove", role="Role to remove")
    @nuke_only()   # <-- changed from admin_only
    async def whitelist_remove(self, interaction: discord.Interaction, user: discord.User = None, role: discord.Role = None):
        if not user and not role:
            return await interaction.response.send_message(embed=BotEmbed.error("Missing Target", "Provide a user or role."), ephemeral=True)
        async with aiosqlite.connect(self.db_path) as db:
            if user:
                await db.execute("DELETE FROM whitelist WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, user.id))
            if role:
                await db.execute("DELETE FROM whitelist WHERE guild_id = ? AND role_id = ?", (interaction.guild_id, role.id))
            await db.commit()
        embed = BotEmbed.success("Removed", "Entry removed from whitelist.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @whitelist_group.command(name="list", description="Show current whitelist")
    @nuke_only()   # <-- changed from admin_only
    async def whitelist_list(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT user_id, role_id FROM whitelist WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message(embed=BotEmbed.info("Whitelist", "The whitelist is empty."), ephemeral=True)
        users = [f"<@{r['user_id']}>" for r in rows if r["user_id"]]
        roles = [f"<@&{r['role_id']}>" for r in rows if r["role_id"]]
        text = "**Users:** " + (", ".join(users) if users else "None") + "\n**Roles:** " + (", ".join(roles) if roles else "None")
        await interaction.response.send_message(embed=BotEmbed.info("Whitelist", text), ephemeral=True)

    # ---------- Error handling for this cog ----------
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(embed=BotEmbed.error("Missing Permissions", "You need `Manage Guild` permission."), ephemeral=True)
        else:
            logger.error(f"Config command error: {error}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))