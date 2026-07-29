import discord
from discord.ext import commands
import aiosqlite
import asyncio
from collections import defaultdict
import time
import json
import logging
import os
from datetime import timedelta          # <-- fixed import
from db import add_log

logger = logging.getLogger("discord.cogs.antinuke")

EVENT_TYPES = [
    "channel_create", "channel_delete",
    "role_create", "role_delete",
    "ban", "kick",
    "webhook_create", "webhook_delete"
]

class AntiNuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = os.getenv("DATABASE_PATH", "./data/security.db")
        self.action_tracker = defaultdict(lambda: defaultdict(list))
        self.cooldowns = {}

    async def get_guild_settings(self, guild_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "modules": json.loads(row["modules"]),
                    "thresholds": json.loads(row["thresholds"]),
                    "time_window": row["time_window"],
                    "punishment": row["punishment"],
                    "quarantine_role_id": row["quarantine_role_id"],
                    "log_channel_id": row["log_channel_id"],
                    "antinuke_enabled": row["antinuke_enabled"]
                }
            else:
                return {
                    "modules": {e: True for e in EVENT_TYPES},
                    "thresholds": {e: 3 for e in EVENT_TYPES},
                    "time_window": 10,
                    "punishment": "strip",
                    "quarantine_role_id": 0,
                    "log_channel_id": 0,
                    "antinuke_enabled": 1
                }

    async def is_whitelisted(self, guild: discord.Guild, user: discord.Member) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT 1 FROM whitelist WHERE guild_id = ? AND user_id = ?", (guild.id, user.id))
            if await cursor.fetchone():
                return True
            for role in user.roles:
                cursor = await db.execute("SELECT 1 FROM whitelist WHERE guild_id = ? AND role_id = ?", (guild.id, role.id))
                if await cursor.fetchone():
                    return True
        return False

    async def punish(self, guild: discord.Guild, user: discord.Member, event_type: str, settings: dict):
        if user.id in self.cooldowns and time.time() - self.cooldowns[user.id] < 30:
            return
        self.cooldowns[user.id] = time.time()

        mode = settings["punishment"]
        log_channel = guild.get_channel(settings["log_channel_id"]) if settings["log_channel_id"] else None
        reason = f"AntiNuke: exceeded {event_type} threshold"
        punishment_taken = ""

        try:
            if mode == "strip":
                perms_to_remove = [
                    "administrator", "manage_channels", "manage_roles",
                    "manage_guild", "ban_members", "kick_members",
                    "manage_webhooks", "manage_emojis", "manage_nicknames"
                ]
                for role in user.roles:
                    if role.is_assignable() and not role.is_bot_managed() and role != guild.default_role:
                        try:
                            new_perms = role.permissions
                            for perm in perms_to_remove:
                                setattr(new_perms, perm, False)
                            await role.edit(permissions=new_perms, reason=f"AntiNuke punishment for {user}")
                        except:
                            pass

                quarantine_role = guild.get_role(settings["quarantine_role_id"])
                if quarantine_role and quarantine_role.is_assignable():
                    await user.add_roles(quarantine_role, reason=reason)
                else:
                    try:
                        await user.timeout(discord.utils.utcnow() + timedelta(hours=1), reason=reason)  # <-- fixed
                    except:
                        pass
                punishment_taken = "strip"

            elif mode == "kick":
                await guild.kick(user, reason=reason)
                punishment_taken = "kick"

            elif mode == "ban":
                await guild.ban(user, reason=reason, delete_message_days=1)
                punishment_taken = "ban"

            # Log to database for dashboard
            await add_log(guild.id, user.id, event_type, punishment_taken)

            # Log to discord channel
            if log_channel:
                embed = discord.Embed(title="🚨 AntiNuke Triggered", color=discord.Color.red(), timestamp=discord.utils.utcnow())
                embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
                embed.add_field(name="Event", value=event_type.replace("_", " ").title())
                embed.add_field(name="Action Taken", value=punishment_taken, inline=False)
                embed.set_footer(text=f"Guild: {guild.name}")
                try:
                    await log_channel.send(embed=embed)
                except:
                    pass

            # Raid alert webhook integration
            raid_alert_cog = self.bot.get_cog("RaidAlert")
            if raid_alert_cog:
                alert_embed = discord.Embed(
                    title="🚨 Anti‑Nuke Triggered",
                    description=f"User {user} ({user.id}) triggered the anti‑nuke system.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                alert_embed.add_field(name="Event", value=event_type.replace("_", " ").title(), inline=True)
                alert_embed.add_field(name="Punishment", value=punishment_taken, inline=True)
                alert_embed.set_footer(text=f"Guild: {guild.name} ({guild.id})")
                await raid_alert_cog.send_alert(guild.id, alert_embed)

        except discord.Forbidden:
            logger.warning(f"Missing permissions to punish {user} in {guild}")
        except Exception as e:
            logger.error(f"Punishment failed for {user}: {e}")

    async def process_event(self, guild: discord.Guild, user: discord.Member, event_type: str):
        # Only ignore our own bot – all other bots (nuke bots) ARE punished
        if user.id == self.bot.user.id:
            return

        settings = await self.get_guild_settings(guild.id)
        if not settings.get("antinuke_enabled", 1):
            return
        if await self.is_whitelisted(guild, user):
            return
        if not settings["modules"].get(event_type, True):
            return

        threshold = settings["thresholds"].get(event_type, 3)
        window = settings["time_window"]
        now = time.time()
        key = (user.id, event_type)
        self.action_tracker[guild.id][key] = [t for t in self.action_tracker[guild.id][key] if now - t < window]
        self.action_tracker[guild.id][key].append(now)

        if len(self.action_tracker[guild.id][key]) >= threshold:
            self.action_tracker[guild.id][key] = []
            logger.info(f"AntiNuke triggered in {guild.name}: {user} for {event_type}")
            await self.punish(guild, user, event_type, settings)

    # --- Event listeners (unchanged) ---
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await asyncio.sleep(0.3)
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    await self.process_event(channel.guild, entry.user, "channel_create")
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await asyncio.sleep(0.3)
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    await self.process_event(channel.guild, entry.user, "channel_delete")
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await asyncio.sleep(0.3)
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    await self.process_event(role.guild, entry.user, "role_create")
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await asyncio.sleep(0.3)
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    await self.process_event(role.guild, entry.user, "role_delete")
        except:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await asyncio.sleep(0.3)
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    await self.process_event(guild, entry.user, "ban")
        except:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await asyncio.sleep(0.3)
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    await self.process_event(member.guild, entry.user, "kick")
                    return
        except:
            pass

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        await asyncio.sleep(0.5)
        guild = channel.guild
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                if entry.target.channel.id == channel.id:
                    await self.process_event(guild, entry.user, "webhook_create")
                    return
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_delete):
                await self.process_event(guild, entry.user, "webhook_delete")
                return
        except:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(AntiNuke(bot))