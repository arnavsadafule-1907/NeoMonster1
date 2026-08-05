import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from checks import admin_only
from formatter import BotEmbed

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

async def is_bot_whitelisted(guild_id: int, bot_id: int) -> bool:
    """Check if a bot is in the whitelist for a guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM bot_whitelist WHERE guild_id = ? AND bot_id = ?", (guild_id, bot_id))
        return await cursor.fetchone() is not None

class BotWhitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    bot_whitelist_group = app_commands.Group(name="botwhitelist", description="Manage trusted bots (ignored by protection systems)")

    @bot_whitelist_group.command(name="add", description="Add a trusted bot to the whitelist")
    @app_commands.describe(bot="Bot to add")
    @admin_only()
    async def bot_whitelist_add(self, interaction: discord.Interaction, bot: discord.User):
        if not bot.bot:
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Bot", "You can only whitelist bot accounts."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO bot_whitelist (guild_id, bot_id) VALUES (?, ?)", (interaction.guild_id, bot.id))
            await db.commit()
        await interaction.response.send_message(embed=BotEmbed.success("Bot Whitelisted", f"{bot.mention} will be ignored by anti‑nuke, spam, and mass mention."), ephemeral=False)

    @bot_whitelist_group.command(name="remove", description="Remove a bot from the whitelist")
    @app_commands.describe(bot="Bot to remove")
    @admin_only()
    async def bot_whitelist_remove(self, interaction: discord.Interaction, bot: discord.User):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM bot_whitelist WHERE guild_id = ? AND bot_id = ?", (interaction.guild_id, bot.id))
            await db.commit()
        await interaction.response.send_message(embed=BotEmbed.success("Bot Removed", f"{bot.mention} is no longer ignored."), ephemeral=False)

    @bot_whitelist_group.command(name="list", description="Show all whitelisted bots")
    @admin_only()
    async def bot_whitelist_list(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT bot_id FROM bot_whitelist WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message(embed=BotEmbed.info("Bot Whitelist", "No bots are currently whitelisted."), ephemeral=True)
        mentions = [f"<@{r['bot_id']}>" for r in rows]
        await interaction.response.send_message(embed=BotEmbed.info("Bot Whitelist", "\n".join(mentions)), ephemeral=True)

async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS bot_whitelist (guild_id INTEGER, bot_id INTEGER, PRIMARY KEY (guild_id, bot_id))")
        await db.commit()
    await bot.add_cog(BotWhitelist(bot))