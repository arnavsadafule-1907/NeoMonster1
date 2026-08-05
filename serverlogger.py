import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from datetime import datetime
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

LOG_TYPES = ["message", "voice", "member", "server", "channel", "role", "emoji", "webhook", "moderation"]

class ServerLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_log_channel(self, guild_id, event_type):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT channel_id FROM log_channels WHERE guild_id = ? AND event_type = ?",
                                      (guild_id, event_type))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def log(self, guild_id, event_type, embed):
        channel_id = await self.get_log_channel(guild_id, event_type)
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)

    # ---------- Message Events ----------
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild: return
        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024] or "*empty*", inline=False)
        if message.attachments:
            embed.add_field(name="Attachments", value="\n".join([a.url for a in message.attachments]), inline=False)
        embed.set_footer(text=f"Message ID: {message.id}")
        await self.log(message.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild or before.content == after.content: return
        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.blue(), timestamp=after.edited_at or datetime.utcnow())
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "*empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*empty*", inline=False)
        embed.set_footer(text=f"Message ID: {before.id}")
        await self.log(before.guild.id, "message", embed)

    # ---------- Voice Events ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        embed = discord.Embed(timestamp=datetime.utcnow(), color=discord.Color.purple())
        if not before.channel and after.channel:
            embed.title = "🔊 Voice Join"
            embed.add_field(name="Member", value=member.mention)
            embed.add_field(name="Channel", value=after.channel.name)
        elif before.channel and not after.channel:
            embed.title = "🔇 Voice Leave"
            embed.add_field(name="Member", value=member.mention)
            embed.add_field(name="Channel", value=before.channel.name)
        elif before.channel and after.channel and before.channel != after.channel:
            embed.title = "↪️ Voice Move"
            embed.add_field(name="Member", value=member.mention)
            embed.add_field(name="From", value=before.channel.name)
            embed.add_field(name="To", value=after.channel.name)
        else: return
        await self.log(member.guild.id, "voice", embed)

    # ---------- Member Events ----------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(title="👤 Member Joined", color=discord.Color.green(), timestamp=datetime.utcnow())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"))
        embed.set_footer(text=f"ID: {member.id}")
        await self.log(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title="👋 Member Left", color=discord.Color.orange(), timestamp=datetime.utcnow())
        embed.add_field(name="Member", value=f"{member} ({member.id})")
        await self.log(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="User", value=f"{user} ({user.id})")
        await self.log(guild.id, "moderation", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(title="🔓 Member Unbanned", color=discord.Color.green(), timestamp=datetime.utcnow())
        embed.add_field(name="User", value=f"{user} ({user.id})")
        await self.log(guild.id, "moderation", embed)

    # ---------- Server/Channel/Role/Emoji/Webhook Events ----------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title="📁 Channel Created", color=discord.Color.blue(), timestamp=datetime.utcnow())
        embed.add_field(name="Name", value=channel.name)
        embed.add_field(name="Type", value=str(channel.type).capitalize())
        await self.log(channel.guild.id, "channel", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title="🗑️ Channel Deleted", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="Name", value=channel.name)
        await self.log(channel.guild.id, "channel", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(title="🎨 Role Created", color=discord.Color.blue(), timestamp=datetime.utcnow())
        embed.add_field(name="Name", value=role.name)
        embed.add_field(name="Color", value=str(role.color))
        await self.log(role.guild.id, "role", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(title="🎨 Role Deleted", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="Name", value=role.name)
        await self.log(role.guild.id, "role", embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        if len(before) < len(after):
            new_emojis = [e for e in after if e not in before]
            for emoji in new_emojis:
                embed = discord.Embed(title="😀 Emoji Added", color=discord.Color.green(), timestamp=datetime.utcnow())
                embed.add_field(name="Name", value=emoji.name)
                embed.set_thumbnail(url=emoji.url)
                await self.log(guild.id, "emoji", embed)
        elif len(before) > len(after):
            removed = [e for e in before if e not in after]
            for emoji in removed:
                embed = discord.Embed(title="😀 Emoji Removed", color=discord.Color.red(), timestamp=datetime.utcnow())
                embed.add_field(name="Name", value=emoji.name)
                await self.log(guild.id, "emoji", embed)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        embed = discord.Embed(title="🪝 Webhooks Updated", color=discord.Color.purple(), timestamp=datetime.utcnow())
        embed.add_field(name="Channel", value=channel.mention)
        await self.log(channel.guild.id, "webhook", embed)

    # ---------- Moderation log hook ----------
    async def log_mod_action(self, guild, staff, action, target, reason=""):
        embed = discord.Embed(title=f"🛠️ {action.upper()}", color=discord.Color.orange(), timestamp=datetime.utcnow())
        embed.add_field(name="Staff", value=staff.mention, inline=True)
        embed.add_field(name="Target", value=target.mention, inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await self.log(guild.id, "moderation", embed)

    # ---------- Log channel setup command (renamed to setlog) ----------
    @app_commands.command(name="setlog", description="Set a log channel for a specific event type")
    @app_commands.describe(event_type="Type of events to log", channel="Channel to send logs to")
    @app_commands.choices(event_type=[app_commands.Choice(name=t, value=t) for t in LOG_TYPES])
    @admin_only()
    async def set_log_channel(self, interaction: discord.Interaction, event_type: str, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO log_channels (guild_id, event_type, channel_id) VALUES (?, ?, ?)",
                             (interaction.guild_id, event_type, channel.id))
            await db.commit()
        embed = BotEmbed.success("Log Channel Set", f"{event_type.capitalize()} logs will be sent to {channel.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS log_channels (
            guild_id INTEGER, event_type TEXT, channel_id INTEGER, PRIMARY KEY (guild_id, event_type))""")
        await db.commit()
    await bot.add_cog(ServerLogger(bot))