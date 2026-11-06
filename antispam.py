from datetime import timedelta
import time
import os
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only, is_extra_owner
from formatter import BotEmbed

def get_db_path() -> str:
    return os.getenv("DATABASE_PATH", "./data/security.db")

FIXED_THRESHOLD = 5
FIXED_WINDOW = 5
FIXED_MUTE_MINUTES = 10


class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_cache: dict[int, dict[int, list[float]]] = {}

    async def is_enabled(self, guild_id: int) -> bool:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT enabled FROM antispam_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return bool(row["enabled"]) if row else True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.id == self.bot.user.id:
            return
        if message.author.id == message.guild.owner_id or message.author.id in self.bot.owner_ids:
            return
        if await is_extra_owner(message.guild.id, message.author.id):
            return

        if message.author.bot:
            try:
                from botwhitelist import is_bot_whitelisted
                if await is_bot_whitelisted(message.guild.id, message.author.id):
                    return
            except ImportError:
                pass

        guild_id = message.guild.id
        if not await self.is_enabled(guild_id):
            return

        created_at = getattr(message, "created_at", None)
        try:
            now = created_at.timestamp() if created_at and hasattr(created_at, "timestamp") else time.time()
        except Exception:
            now = time.time()

        cache = self.spam_cache.setdefault(guild_id, {}).setdefault(message.author.id, [])
        cache = [t for t in cache if now - t < FIXED_WINDOW]
        cache.append(now)
        self.spam_cache[guild_id][message.author.id] = cache

        if len(cache) >= FIXED_THRESHOLD:
            try:
                until = discord.utils.utcnow() + timedelta(minutes=FIXED_MUTE_MINUTES)
                if isinstance(message.author, discord.Member):
                    await message.author.timeout(until, reason="Spam detected (AntiSpam)")
            except (discord.Forbidden, discord.HTTPException):
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
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute("INSERT OR IGNORE INTO antispam_settings (guild_id, enabled) VALUES (?, 1)", (guild_id,))
            await db.commit()

        if action == "enable":
            async with aiosqlite.connect(get_db_path()) as db:
                await db.execute("UPDATE antispam_settings SET enabled = 1 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.success("Anti-Spam Enabled", "Anti-spam protection is now **enabled**.")
            await interaction.response.send_message(embed=embed)
        elif action == "disable":
            async with aiosqlite.connect(get_db_path()) as db:
                await db.execute("UPDATE antispam_settings SET enabled = 0 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.warning("Anti-Spam Disabled", "Anti-spam protection is now **disabled**.")
            await interaction.response.send_message(embed=embed)
        elif action == "status":
            enabled = await self.is_enabled(guild_id)
            embed = BotEmbed.info(
                "Anti-Spam Status",
                f"Status: **{'Enabled ✅' if enabled else 'Disabled ❌'}**\n"
                f"Threshold: **{FIXED_THRESHOLD}** messages per **{FIXED_WINDOW}** seconds\n"
                f"Punishment: **{FIXED_MUTE_MINUTES}** minute timeout"
            )
            await interaction.response.send_message(embed=embed)

async def setup(bot):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antispam_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                threshold INTEGER DEFAULT 5,
                window INTEGER DEFAULT 5,
                mute_duration INTEGER DEFAULT 10
            )
        """)
        await db.commit()
    await bot.add_cog(AntiSpam(bot))
