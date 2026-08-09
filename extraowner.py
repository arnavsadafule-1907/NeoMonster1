import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

async def is_extra_owner(guild_id: int, user_id: int) -> bool:
    """Check if a user is an extra owner for the given guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM extra_owners WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        return await cursor.fetchone() is not None

class ExtraOwner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        """Only the global bot owner or the server owner can manage extra owners."""
        # Global bot owner (IDs from .env)
        if interaction.user.id in interaction.client.owner_ids:
            return True
        # Server owner
        if interaction.user.id == interaction.guild.owner_id:
            return True
        return False

    # ---------- /addowner ----------
    @app_commands.command(name="addowner", description="Add an extra owner (can bypass all role checks)")
    @app_commands.describe(user="User to promote")
    async def add_owner(self, interaction: discord.Interaction, user: discord.User):
        if not self._is_authorized(interaction):
            embed = BotEmbed.error("Permission Denied", "Only the global bot owner or the server owner can add extra owners.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Don't add the actual owner (they already have full power)
        if user.id == interaction.guild.owner_id:
            embed = BotEmbed.error("Invalid", "The server owner is already the highest authority.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Check if already an extra owner
        if await is_extra_owner(interaction.guild_id, user.id):
            embed = BotEmbed.warning("Already Owner", f"{user.mention} is already an extra owner.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO extra_owners (guild_id, user_id) VALUES (?, ?)",
                (interaction.guild_id, user.id)
            )
            await db.commit()

        embed = BotEmbed.success("Extra Owner Added", f"{user.mention} now has owner‑level access in this server.")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # ---------- /removeowner ----------
    @app_commands.command(name="removeowner", description="Remove an extra owner")
    @app_commands.describe(user="User to demote")
    async def remove_owner(self, interaction: discord.Interaction, user: discord.User):
        if not self._is_authorized(interaction):
            embed = BotEmbed.error("Permission Denied", "Only the global bot owner or the server owner can remove extra owners.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not await is_extra_owner(interaction.guild_id, user.id):
            embed = BotEmbed.error("Not an Owner", f"{user.mention} is not an extra owner.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM extra_owners WHERE guild_id = ? AND user_id = ?",
                (interaction.guild_id, user.id)
            )
            await db.commit()

        embed = BotEmbed.success("Extra Owner Removed", f"{user.mention} has been demoted.")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # ---------- /listowners ----------
    @app_commands.command(name="listowners", description="Show all extra owners in this server")
    async def list_owners(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT user_id FROM extra_owners WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()

        if not rows:
            embed = BotEmbed.info("Extra Owners", "No extra owners have been added.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        mentions = [f"<@{r['user_id']}>" for r in rows]
        embed = BotEmbed.info("Extra Owners", "\n".join(mentions))
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS extra_owners (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.commit()
    await bot.add_cog(ExtraOwner(bot))