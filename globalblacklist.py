import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class GlobalBlacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_blacklisted(self, user_id: int) -> bool:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT 1 FROM global_blacklist WHERE user_id = ?", (user_id,))
                return await cursor.fetchone() is not None
        except Exception:
            return False

    async def is_guild_blacklisted(self, guild_id: int) -> bool:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (guild_id,))
                return await cursor.fetchone() is not None
        except Exception:
            return False

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if await self.is_guild_blacklisted(guild.id):
            await guild.leave()
            try:
                await guild.owner.send("⚠️ Your server is blacklisted from using NeoMonster due to abuse.")
            except:
                pass

    @app_commands.command(name="blacklist", description="Globally blacklist a user (owner only)")
    @app_commands.describe(user_id="User ID to blacklist")
    async def blacklist_add(self, interaction: discord.Interaction, user_id: str):
        if interaction.user.id not in self.bot.owner_ids:
            await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=False)
            return
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("Invalid user ID.", ephemeral=False)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO global_blacklist (user_id) VALUES (?)", (uid,))
            await db.commit()
        await interaction.response.send_message(f"User `{uid}` blacklisted globally.", ephemeral=False)

    @app_commands.command(name="unblacklist", description="Remove a global blacklist")
    @app_commands.describe(user_id="User ID to unblacklist")
    async def blacklist_remove(self, interaction: discord.Interaction, user_id: str):
        if interaction.user.id not in self.bot.owner_ids:
            await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=False)
            return
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("Invalid user ID.", ephemeral=False)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM global_blacklist WHERE user_id = ?", (uid,))
            await db.commit()
        await interaction.response.send_message(f"User `{uid}` removed from blacklist.", ephemeral=False)

async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS global_blacklist (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS guild_blacklist (guild_id INTEGER PRIMARY KEY)")
        await db.commit()
    await bot.add_cog(GlobalBlacklist(bot))