import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")


class Sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- DB helpers ----------
    async def get_sticky(self, channel_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sticky_messages WHERE channel_id = ?",
                (channel_id,)
            )
            return await cursor.fetchone()

    async def update_last_message(self, channel_id: int, message_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE sticky_messages SET last_message_id = ? WHERE channel_id = ?",
                (message_id, channel_id)
            )
            await db.commit()

    # ---------- Auto re-post ----------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        sticky = await self.get_sticky(message.channel.id)
        if not sticky or not sticky["enabled"]:
            return

        # Delete the previous sticky message
        last_id = sticky["last_message_id"]
        if last_id:
            try:
                old = await message.channel.fetch_message(last_id)
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        # Post a fresh sticky at the bottom
        try:
            new_msg = await message.channel.send(sticky["content"])
            await self.update_last_message(message.channel.id, new_msg.id)
        except discord.Forbidden:
            pass

    # ---------- /stick ----------
    @app_commands.command(name="stick", description="Set a sticky message in the current channel")
    @app_commands.describe(content="The sticky message content (markdown supported)")
    @staff_only()
    async def stick(self, interaction: discord.Interaction, content: str):
        await interaction.response.defer(ephemeral=True)

        # Remove existing sticky message if present
        existing = await self.get_sticky(interaction.channel_id)
        if existing and existing["last_message_id"]:
            try:
                old = await interaction.channel.fetch_message(existing["last_message_id"])
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        # Send new sticky
        try:
            sticky_msg = await interaction.channel.send(content)
        except discord.Forbidden:
            return await interaction.followup.send(
                embed=BotEmbed.error("Permission Denied", "I cannot send messages in this channel."),
                ephemeral=True
            )

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sticky_messages "
                "(channel_id, guild_id, content, last_message_id, enabled) "
                "VALUES (?, ?, ?, ?, 1)",
                (interaction.channel_id, interaction.guild_id, content, sticky_msg.id)
            )
            await db.commit()

        await interaction.followup.send(
            embed=BotEmbed.success("Sticky Set", f"Sticky message set in {interaction.channel.mention}."),
            ephemeral=True
        )

    # ---------- /stickstop ----------
    @app_commands.command(name="stickstop", description="Disable the sticky message in this channel")
    @staff_only()
    async def stickstop(self, interaction: discord.Interaction):
        existing = await self.get_sticky(interaction.channel_id)
        if not existing:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Sticky", "There is no sticky message in this channel."),
                ephemeral=True
            )

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE sticky_messages SET enabled = 0 WHERE channel_id = ?",
                (interaction.channel_id,)
            )
            await db.commit()

        await interaction.response.send_message(
            embed=BotEmbed.success("Sticky Disabled", "The sticky message has been disabled."),
            ephemeral=True
        )

    # ---------- /stickremove ----------
    @app_commands.command(name="stickremove", description="Remove the sticky message from this channel")
    @staff_only()
    async def stickremove(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        existing = await self.get_sticky(interaction.channel_id)
        if not existing:
            return await interaction.followup.send(
                embed=BotEmbed.info("No Sticky", "There is no sticky message in this channel."),
                ephemeral=True
            )

        # Delete last posted sticky from the channel
        if existing["last_message_id"]:
            try:
                old = await interaction.channel.fetch_message(existing["last_message_id"])
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sticky_messages WHERE channel_id = ?", (interaction.channel_id,))
            await db.commit()

        await interaction.followup.send(
            embed=BotEmbed.success("Sticky Removed", "The sticky message has been removed."),
            ephemeral=True
        )

    # ---------- /sticklist ----------
    @app_commands.command(name="sticklist", description="List all sticky messages in this server")
    @staff_only()
    async def sticklist(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sticky_messages WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Stickies", "No sticky messages in this server."),
                ephemeral=True
            )

        embed = BotEmbed.info("Sticky Messages")
        for row in rows:
            status = "🟢 Enabled" if row["enabled"] else "🔴 Disabled"
            preview = row["content"][:80] + ("..." if len(row["content"]) > 80 else "")
            embed.add_field(
                name=f"<#{row['channel_id']}> – {status}",
                value=preview,
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sticky_messages (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                last_message_id INTEGER,
                enabled INTEGER DEFAULT 1
            )
        """)
        await db.commit()
    await bot.add_cog(Sticky(bot))