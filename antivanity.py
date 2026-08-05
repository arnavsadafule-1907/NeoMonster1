import discord
from discord import app_commands
from discord.ext import commands
import re
import aiosqlite
import os
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class AntiVanity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_enabled(self, guild_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT enabled FROM antivanity_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return bool(row["enabled"]) if row else False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if not await self.is_enabled(message.guild.id):
            return

        # Check for custom Discord invite links (not discord.gg/random)
        # Pattern: discord.gg/ or discord.com/invite/ followed by a known custom slug
        invites = re.findall(r'(?:discord\.gg/|discord\.com/invite/)(\w+)', message.content)
        if invites:
            # Allow if the user has Manage Server (staff can post invites)
            if message.author.guild_permissions.manage_guild:
                return
            try:
                await message.delete()
                await message.author.send(embed=BotEmbed.warning(
                    "Invite Blocked",
                    "Your message contained a Discord invite link. Only staff may post invites."
                ))
            except:
                pass

    @app_commands.command(name="antivanity", description="Enable/disable vanity URL blocking")
    @app_commands.describe(action="Enable or disable")
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
    ])
    @admin_only()
    async def antivanity(self, interaction: discord.Interaction, action: str):
        guild_id = interaction.guild_id
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO antivanity_settings (guild_id, enabled) VALUES (?, 0)", (guild_id,))
            await db.commit()
            if action == "enable":
                await db.execute("UPDATE antivanity_settings SET enabled = 1 WHERE guild_id = ?", (guild_id,))
            else:
                await db.execute("UPDATE antivanity_settings SET enabled = 0 WHERE guild_id = ?", (guild_id,))
            await db.commit()
        embed = BotEmbed.success("Anti-Vanity", f"{'Enabled' if action == 'enable' else 'Disabled'}.")
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antivanity_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0
            )
        """)
        await db.commit()
    await bot.add_cog(AntiVanity(bot))