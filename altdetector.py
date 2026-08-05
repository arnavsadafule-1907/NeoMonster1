import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from datetime import datetime, timedelta, timezone
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class AltDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_settings(self, guild_id: int) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM altdetector_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            if row:
                return {"enabled": bool(row["enabled"]), "min_days": row["min_days"], "log_channel_id": row["log_channel_id"]}
            return {"enabled": False, "min_days": 7, "log_channel_id": None}

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await self.get_settings(member.guild.id)
        if not settings["enabled"] or not settings["log_channel_id"]:
            return

        account_age = datetime.now(timezone.utc) - member.created_at
        if account_age < timedelta(days=settings["min_days"]):
            channel = member.guild.get_channel(settings["log_channel_id"])
            if channel:
                embed = discord.Embed(
                    title="⚠️ Suspicious Account Detected",
                    description=f"{member.mention} joined with an account created **{account_age.days} days ago**.",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"))
                embed.add_field(name="User ID", value=member.id)
                embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed)

    @app_commands.command(name="altdetector", description="Configure alt account detection")
    @app_commands.describe(action="Setting to change", value="Value for settings")
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
        app_commands.Choice(name="min_days", value="min_days"),
        app_commands.Choice(name="channel", value="channel"),
    ])
    @admin_only()
    async def altdetector(self, interaction: discord.Interaction, action: str, value: str = None):
        guild_id = interaction.guild_id
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO altdetector_settings (guild_id) VALUES (?)", (guild_id,))
            await db.commit()

        if action == "enable":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE altdetector_settings SET enabled = 1 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.success("Alt Detector", "Enabled.")
        elif action == "disable":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE altdetector_settings SET enabled = 0 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.success("Alt Detector", "Disabled.")
        elif action == "min_days":
            if not value or not value.isdigit():
                embed = BotEmbed.error("Invalid", "Provide a number of days.")
                return await interaction.response.send_message(embed=embed, ephemeral=False)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE altdetector_settings SET min_days = ? WHERE guild_id = ?", (int(value), guild_id))
                await db.commit()
            embed = BotEmbed.success("Min Days Updated", f"Accounts newer than `{value}` days will be flagged.")
        elif action == "channel":
            try:
                channel = await commands.TextChannelConverter().convert(interaction, value)
            except:
                embed = BotEmbed.error("Invalid Channel", "Mention a valid text channel.")
                return await interaction.response.send_message(embed=embed, ephemeral=False)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE altdetector_settings SET log_channel_id = ? WHERE guild_id = ?", (channel.id, guild_id))
                await db.commit()
            embed = BotEmbed.success("Log Channel Set", f"Alerts will be sent to {channel.mention}.")
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS altdetector_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                min_days INTEGER DEFAULT 7,
                log_channel_id INTEGER
            )
        """)
        await db.commit()
    await bot.add_cog(AltDetector(bot))