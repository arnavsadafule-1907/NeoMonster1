import asyncio
from collections import defaultdict
from datetime import timedelta
import json
import logging
import os
import time
import aiosqlite
import discord
from discord.ext import commands
from checks import is_extra_owner
from db import add_log, get_db_path

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
        self.db_path = get_db_path()
        self.action_tracker = defaultdict(lambda: defaultdict(list))
        self.cooldowns: dict[int, float] = {}
        self._lock = asyncio.Lock()

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
            return {
                "modules": {e: True for e in EVENT_TYPES},
                "thresholds": {e: 3 for e in EVENT_TYPES},
                "time_window": 10,
                "punishment": "strip",
                "quarantine_role_id": 0,
                "log_channel_id": 0,
                "antinuke_enabled": 1
            }

    async def is_whitelisted(self, guild: discord.Guild, user: discord.Member | discord.User) -> bool:
        if await is_extra_owner(guild.id, user.id):
            return True
        user_roles = [r.id for r in getattr(user, "roles", []) if hasattr(r, "id")]
        async with aiosqlite.connect(self.db_path, timeout=10.0) as db:
            if user_roles:
                placeholders = ",".join("?" for _ in user_roles)
                query = f"SELECT 1 FROM whitelist WHERE guild_id = ? AND (user_id = ? OR role_id IN ({placeholders})) LIMIT 1"  # nosec B608
                params = [guild.id, user.id, *user_roles]
            else:
                query = "SELECT 1 FROM whitelist WHERE guild_id = ? AND user_id = ? LIMIT 1"
                params = [guild.id, user.id]
            cursor = await db.execute(query, params)
            return await cursor.fetchone() is not None

    async def punish(self, guild: discord.Guild, user: discord.Member | discord.User, event_type: str, settings: dict):
        if user.id == guild.owner_id or user.id in self.bot.owner_ids:
            return
        if await is_extra_owner(guild.id, user.id):
            return

        now = time.time()
        if user.id in self.cooldowns and now - self.cooldowns[user.id] < 30:
            return
        self.cooldowns[user.id] = now

        mode = settings.get("punishment", "strip")
        log_channel = guild.get_channel(settings["log_channel_id"]) if settings.get("log_channel_id") else None
        reason = f"AntiNuke: exceeded {event_type} threshold"
        punishment_taken = mode

        try:
            if isinstance(user, discord.Member):
                if mode == "strip":
                    roles_to_remove = [
                        role for role in user.roles
                        if role.is_assignable() and not role.is_bot_managed() and role != guild.default_role and (
                            role.permissions.administrator
                            or role.permissions.manage_channels
                            or role.permissions.manage_roles
                            or role.permissions.manage_guild
                            or role.permissions.ban_members
                            or role.permissions.kick_members
                            or role.permissions.manage_webhooks
                        )
                    ]
                    if roles_to_remove:
                        try:
                            await user.remove_roles(*roles_to_remove, reason=reason)
                        except (discord.Forbidden, discord.HTTPException):
                            pass

                    quarantine_role_id = settings.get("quarantine_role_id", 0)
                    quarantine_role = guild.get_role(quarantine_role_id) if quarantine_role_id else None
                    if quarantine_role and quarantine_role.is_assignable():
                        try:
                            await user.add_roles(quarantine_role, reason=reason)
                        except (discord.Forbidden, discord.HTTPException):
                            pass
                    else:
                        try:
                            await user.timeout(discord.utils.utcnow() + timedelta(hours=1), reason=reason)
                        except (discord.Forbidden, discord.HTTPException):
                            pass
                    punishment_taken = "strip"

                elif mode == "kick":
                    await guild.kick(user, reason=reason)
                    punishment_taken = "kick"

                elif mode == "ban":
                    await guild.ban(user, reason=reason, delete_message_days=1)
                    punishment_taken = "ban"
            else:
                if mode == "ban":
                    await guild.ban(user, reason=reason, delete_message_days=1)
                    punishment_taken = "ban"

            await add_log(guild.id, user.id, event_type, punishment_taken)

            if log_channel:
                title = "🚨 AntiNuke Triggered"
                embed = discord.Embed(title=title, color=discord.Color.red(), timestamp=discord.utils.utcnow())
                embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
                embed.add_field(name="Event", value=event_type.replace("_", " ").title())
                embed.add_field(name="Action Taken", value=punishment_taken, inline=False)
                embed.set_footer(text=f"Guild: {guild.name}")
                try:
                    await log_channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

            raid_alert_cog = self.bot.get_cog("RaidAlert")
            if raid_alert_cog and hasattr(raid_alert_cog, "send_alert"):
                title = "🚨 AntiNuke Triggered"
                alert_embed = discord.Embed(
                    title=title,
                    description=f"User {user} ({user.id}) triggered the anti-nuke system.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                alert_embed.add_field(name="Event", value=event_type.replace("_", " ").title(), inline=True)
                alert_embed.add_field(name="Punishment", value=punishment_taken, inline=True)
                alert_embed.set_footer(text=f"Guild: {guild.name} ({guild.id})")
                try:
                    await raid_alert_cog.send_alert(guild.id, alert_embed)
                except Exception:
                    pass

        except discord.Forbidden:
            logger.warning(f"Missing permissions to punish {user} in {guild}")
        except Exception as e:
            logger.error(f"Punishment failed for {user}: {e}")

    async def process_event(self, guild: discord.Guild, user: discord.Member | discord.User, event_type: str):
        if user.id == self.bot.user.id or user.id == guild.owner_id or user.id in self.bot.owner_ids:
            return
        if await is_extra_owner(guild.id, user.id):
            return

        if not isinstance(user, discord.Member):
            member = guild.get_member(user.id)
            if member is None:
                try:
                    member = await guild.fetch_member(user.id)
                except (discord.NotFound, discord.HTTPException):
                    member = None
            if member is not None:
                user = member

        if user.bot:
            try:
                from botwhitelist import is_bot_whitelisted
                if await is_bot_whitelisted(guild.id, user.id):
                    return
            except ImportError:
                pass

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

        async with self._lock:
            self.action_tracker[guild.id][key] = [t for t in self.action_tracker[guild.id][key] if now - t < window]
            self.action_tracker[guild.id][key].append(now)
            count = len(self.action_tracker[guild.id][key])
            if count >= threshold:
                self.action_tracker[guild.id][key] = []
                should_punish = True
            else:
                should_punish = False

        if should_punish:
            logger.info(f"AntiNuke triggered in {guild.name}: {user} for {event_type}")
            await self.punish(guild, user, event_type, settings)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await asyncio.sleep(0.3)
        try:
            async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
                if entry.target and entry.target.id == channel.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                        await self.process_event(channel.guild, entry.user, "channel_create")
                        break
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await asyncio.sleep(0.3)
        try:
            async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target and entry.target.id == channel.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                        await self.process_event(channel.guild, entry.user, "channel_delete")
                        break
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await asyncio.sleep(0.3)
        try:
            async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                if entry.target and entry.target.id == role.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                        await self.process_event(role.guild, entry.user, "role_create")
                        break
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await asyncio.sleep(0.3)
        try:
            async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
                if entry.target and entry.target.id == role.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                        await self.process_event(role.guild, entry.user, "role_delete")
                        break
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        await asyncio.sleep(0.3)
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target and entry.target.id == user.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                        await self.process_event(guild, entry.user, "ban")
                        break
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await asyncio.sleep(0.3)
        try:
            async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                if entry.target and entry.target.id == member.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                        await self.process_event(member.guild, entry.user, "kick")
                        return
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        await asyncio.sleep(0.5)
        guild = channel.guild
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_create):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                    target_channel = getattr(entry.target, "channel", None)
                    if target_channel and target_channel.id == channel.id:
                        await self.process_event(guild, entry.user, "webhook_create")
                        return
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_delete):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() < 20:
                    await self.process_event(guild, entry.user, "webhook_delete")
                    return
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiNuke(bot))
