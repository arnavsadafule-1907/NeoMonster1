import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import os
from datetime import datetime, timezone
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class StaffLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def add_log(self, guild_id: int, staff_id: int, action: str, target_id: int = None, reason: str = None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO staff_logs (guild_id, staff_id, action, target_id, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, staff_id, action, target_id, reason, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()

    # Hook into moderation events
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await asyncio.sleep(0.3)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                await self.add_log(guild.id, entry.user.id, "ban", user.id, entry.reason)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await asyncio.sleep(0.3)
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                await self.add_log(member.guild.id, entry.user.id, "kick", member.id, entry.reason)

    @app_commands.command(name="stafflog", description="View a staff member's activity log")
    @app_commands.describe(user="Staff member to check", limit="Number of entries (max 50)")
    @admin_only()
    async def stafflog(self, interaction: discord.Interaction, user: discord.User, limit: int = 10):
        limit = min(limit, 50)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM staff_logs WHERE guild_id = ? AND staff_id = ? ORDER BY id DESC LIMIT ?",
                (interaction.guild_id, user.id, limit)
            )
            logs = await cursor.fetchall()

        if not logs:
            embed = BotEmbed.info("No Logs", f"No activity found for {user.mention}.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = BotEmbed.info(f"Staff Activity Log – {user.display_name}")
        for log in logs:
            timestamp = log["timestamp"][:19].replace("T", " ")
            target_mention = f"<@{log['target_id']}>" if log["target_id"] else "N/A"
            reason_text = log["reason"] or "No reason"
            embed.add_field(
                name=f"{timestamp} – {log['action'].upper()}",
                value=f"Target: {target_mention}\nReason: {reason_text}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    import asyncio  # needed for the listener
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS staff_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                staff_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_id INTEGER,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        await db.commit()
    await bot.add_cog(StaffLog(bot))