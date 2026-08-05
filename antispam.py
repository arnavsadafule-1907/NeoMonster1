import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from datetime import timedelta
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

FIXED_THRESHOLD = 5
FIXED_WINDOW = 5
FIXED_MUTE_MINUTES = 10

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_cache = {}

    async def is_enabled(self, guild_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT enabled FROM antispam_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return bool(row["enabled"]) if row else True

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.author.bot:
            from botwhitelist import is_bot_whitelisted
            if not await is_bot_whitelisted(message.guild.id, message.author.id):
                return  # ignore bots that aren't whitelisted
        guild_id = message.guild.id
        if not await self.is_enabled(guild_id):
            return

        now = message.created_at.timestamp()
        cache = self.spam_cache.setdefault(guild_id, {}).setdefault(message.author.id, [])
        cache = [t for t in cache if now - t < FIXED_WINDOW]
        cache.append(now)
        self.spam_cache[guild_id][message.author.id] = cache

        if len(cache) >= FIXED_THRESHOLD:
            try:
                until = discord.utils.utcnow() + timedelta(minutes=FIXED_MUTE_MINUTES)
                await message.author.timeout(until, reason="Spam detected (AntiSpam)")
            except discord.Forbidden:
                pass
            self.spam_cache[guild_id][message.author.id] = []

    @app_commands.command(name="antispam", description="Enable, disable, or check anti-spam status")
    @app_commands.describe(action="What to do")
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
        app_commands.Choice(name="status", value="status"),
    ])
    @admin_only()
    async def antispam(self, interaction: discord.Interaction, action: str):
        guild_id = interaction.guild_id
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO antispam_settings (guild_id, enabled) VALUES (?, 1)", (guild_id,))
            await db.commit()

        if action == "enable":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE antispam_settings SET enabled = 1 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.success("Anti‑Spam Enabled", f"Detection: {FIXED_THRESHOLD} msgs in {FIXED_WINDOW}s → {FIXED_MUTE_MINUTES} min mute.")
        elif action == "disable":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE antispam_settings SET enabled = 0 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.success("Anti‑Spam Disabled", "Spam detection turned off.")
        elif action == "status":
            enabled = await self.is_enabled(guild_id)
            status_text = "Enabled" if enabled else "Disabled"
            embed = BotEmbed.info("Anti‑Spam Status", f"Status: **{status_text}**\nThreshold: {FIXED_THRESHOLD} msgs / {FIXED_WINDOW}s\nMute duration: {FIXED_MUTE_MINUTES} min.")
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antispam_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 1
            )
        """)
        await db.commit()
    await bot.add_cog(AntiSpam(bot))