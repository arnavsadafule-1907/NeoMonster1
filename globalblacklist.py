import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class GlobalBlacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_blacklisted(self, user_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM global_blacklist WHERE user_id = ?", (user_id,))
            return await cursor.fetchone() is not None

    async def is_guild_blacklisted(self, guild_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchone() is not None

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if await self.is_blacklisted(interaction.user.id):
            embed = BotEmbed.error("Blacklisted", "You are blacklisted from using NeoMonster.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            raise commands.CommandError("User blacklisted")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if await self.is_guild_blacklisted(guild.id):
            await guild.leave()
            try:
                await guild.owner.send("⚠️ Your server is blacklisted from using NeoMonster due to abuse.")
            except:
                pass

    @app_commands.command(name="blacklist", description="Blacklist a user globally (owner only)")
    @app_commands.describe(user_id="User ID to blacklist")
    async def blacklist_add(self, interaction: discord.Interaction, user_id: str):
        if interaction.user.id not in self.bot.owner_ids:
            embed = BotEmbed.error("Permission Denied", "Only the bot owner can use this command.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            uid = int(user_id)
        except ValueError:
            embed = BotEmbed.error("Invalid", "Provide a valid user ID.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO global_blacklist (user_id) VALUES (?)", (uid,))
            await db.commit()
        embed = BotEmbed.success("Blacklisted", f"User `{uid}` has been globally blacklisted.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unblacklist", description="Remove a user from global blacklist")
    @app_commands.describe(user_id="User ID to unblacklist")
    async def blacklist_remove(self, interaction: discord.Interaction, user_id: str):
        if interaction.user.id not in self.bot.owner_ids:
            embed = BotEmbed.error("Permission Denied", "Only the bot owner can use this command.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            uid = int(user_id)
        except ValueError:
            embed = BotEmbed.error("Invalid", "Provide a valid user ID.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM global_blacklist WHERE user_id = ?", (uid,))
            await db.commit()
        embed = BotEmbed.success("Unblacklisted", f"User `{uid}` has been removed from the blacklist.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS global_blacklist (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS guild_blacklist (guild_id INTEGER PRIMARY KEY)")
        await db.commit()
    await bot.add_cog(GlobalBlacklist(bot))