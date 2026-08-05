import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class MessageLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_log_channel(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT log_channel_id FROM guild_message_log WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return row["log_channel_id"] if row else None

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        channel_id = await self.get_log_channel(message.guild.id)
        if not channel_id:
            return
        log_channel = message.guild.get_channel(channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024] or "*empty*", inline=False)
        if message.attachments:
            embed.add_field(name="Attachments", value="\n".join([a.url for a in message.attachments]), inline=False)
        embed.set_footer(text=f"Message ID: {message.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:  # only content changed
            return
        channel_id = await self.get_log_channel(before.guild.id)
        if not channel_id:
            return
        log_channel = before.guild.get_channel(channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.blue(), timestamp=after.edited_at or discord.utils.utcnow())
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "*empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*empty*", inline=False)
        embed.set_footer(text=f"Message ID: {before.id}")
        await log_channel.send(embed=embed)

    @app_commands.command(name="messagelog", description="Set the channel for message logs")
    @app_commands.describe(channel="Channel to log deleted/edited messages")
    @admin_only()
    async def messagelog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO guild_message_log (guild_id, log_channel_id) VALUES (?, ?)", (interaction.guild_id, channel.id))
            await db.commit()
        embed = BotEmbed.success("Message Log Channel Set", f"Message logs will be sent to {channel.mention}.")
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_message_log (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER NOT NULL
            )
        """)
        await db.commit()
    await bot.add_cog(MessageLog(bot))