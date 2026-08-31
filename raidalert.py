import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import aiohttp
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class RaidAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        # We'll hook into the anti‑nuke cog's internal punish method via a simple custom event
        pass  # This is handled differently – we'll add the webhook call directly in antinuke.py

    @app_commands.command(name="raidwebhook", description="Set a webhook URL for raid alerts")
    @app_commands.describe(url="Discord webhook URL to receive alerts")
    @admin_only()
    async def set_webhook(self, interaction: discord.Interaction, url: str):
        if not url.startswith("https://discord.com/api/webhooks/"):
            embed = BotEmbed.error("Invalid URL", "Must be a Discord webhook URL.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO raid_webhooks (guild_id, webhook_url) VALUES (?, ?)", (interaction.guild_id, url))
            await db.commit()
        embed = BotEmbed.success("Webhook Set", "Raid alerts will be sent to that webhook.")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def send_alert(self, guild_id: int, embed: discord.Embed):
        """Called by antinuke.py when a punishment occurs."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT webhook_url FROM raid_webhooks WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            if not row:
                return
            webhook_url = row["webhook_url"]
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, session=session)
            await webhook.send(embed=embed, username="NeoMonster Raid Alert")


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS raid_webhooks (
                guild_id INTEGER PRIMARY KEY,
                webhook_url TEXT NOT NULL
            )
        """)
        await db.commit()
    await bot.add_cog(RaidAlert(bot))