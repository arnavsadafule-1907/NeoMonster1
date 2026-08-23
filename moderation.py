import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from datetime import timedelta
from checks import staff_only
from formatter import BotEmbed

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Log channel helpers ----------
    async def get_mod_log_channel(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT mod_log_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_mod_log_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE guild_settings SET mod_log_channel_id = ? WHERE guild_id = ?",
                (channel_id, guild_id)
            )
            await db.commit()

    # ---------- Command to set the log channel ----------
    @app_commands.command(name="setmodlog", description="Set the channel for moderation logs")
    @app_commands.describe(channel="The channel where moderation actions will be logged")
    @staff_only()
    async def set_modlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.set_mod_log_channel(interaction.guild_id, channel.id)
        embed = BotEmbed.success("Moderation Log Set", f"Logs will be sent to {channel.mention}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Internal log method ----------
    async def _log(self, guild, moderator, action, target, reason=None, duration=None):
        channel_id = await self.get_mod_log_channel(guild.id)
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title=f"🔨 {action}",
            color=0x3B82F6,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Target", value=target.mention, inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if duration:
            embed.add_field(name="Duration", value=duration, inline=True)
        embed.set_footer(text=f"User ID: {target.id}")

        try:
            await channel.send(embed=embed)
        except:
            pass

    # ---------- BAN ----------
    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.describe(member="Member to ban", reason="Reason for ban")
    @staff_only()
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            embed = BotEmbed.error("Permission Denied", "You cannot ban this member.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)
        try:
            await member.ban(reason=reason)
            embed = BotEmbed.success("Member Banned", f"{member.mention} has been banned.\n**Reason:** {reason}")
            await self._log(interaction.guild, interaction.user, "Ban", member, reason)
        except discord.Forbidden:
            embed = BotEmbed.error("Missing Permissions", "I don't have permission to ban this member.")
        await interaction.response.send_message(embed=embed)

    # ---------- KICK ----------
    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @staff_only()
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            await member.kick(reason=reason)
            embed = BotEmbed.success("Member Kicked", f"{member.mention} has been kicked.\n**Reason:** {reason}")
            await self._log(interaction.guild, interaction.user, "Kick", member, reason)
        except discord.Forbidden:
            embed = BotEmbed.error("Missing Permissions", "I don't have permission to kick this member.")
        await interaction.response.send_message(embed=embed)

    # ---------- MUTE ----------
    @app_commands.command(name="mute", description="Timeout a member")
    @app_commands.describe(member="Member to mute", duration="Duration in minutes", reason="Reason")
    @staff_only()
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        if member.is_timed_out():
            embed = BotEmbed.warning("Already Muted", f"{member.mention} is already muted.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)
        try:
            until = discord.utils.utcnow() + timedelta(minutes=duration)
            await member.timeout(until, reason=reason)
            embed = BotEmbed.success("Member Muted", f"{member.mention} has been muted for {duration} minutes.\n**Reason:** {reason}")
            await self._log(interaction.guild, interaction.user, "Mute", member, reason, f"{duration} minutes")
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I cannot mute this member. Ensure I have **Moderate Members** permission and my role is above theirs.")
        await interaction.response.send_message(embed=embed)

    # ---------- UNMUTE ----------
    @app_commands.command(name="unmute", description="Remove a timeout from a member")
    @app_commands.describe(member="Member to unmute")
    @staff_only()
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not member.is_timed_out():
            embed = BotEmbed.warning("Not Muted", f"{member.mention} is not currently timed out.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)
        try:
            await member.timeout(None, reason="Unmute")
            embed = BotEmbed.success("Member Unmuted", f"{member.mention} has been unmuted.")
            await self._log(interaction.guild, interaction.user, "Unmute", member, "No reason")
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I cannot unmute this member.")
        await interaction.response.send_message(embed=embed)

    # ---------- WARN ----------
    @app_commands.command(name="warn", description="Warn a member (log only)")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @staff_only()
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            await member.send(embed=BotEmbed.warning("You were warned", f"**Server:** {interaction.guild.name}\n**Reason:** {reason}"))
        except:
            pass
        embed = BotEmbed.success("Warning Issued", f"{member.mention} has been warned.\n**Reason:** {reason}")
        await interaction.response.send_message(embed=embed)
        await self._log(interaction.guild, interaction.user, "Warn", member, reason)

    # ---------- PURGE ----------
    @app_commands.command(name="purge", description="Delete a number of messages")
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @staff_only()
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            embed = BotEmbed.error("Invalid Amount", "Please enter a number between 1 and 100.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
            embed = BotEmbed.success("Messages Purged", f"Deleted {len(deleted)} messages.")
            await self._log(interaction.guild, interaction.user, "Purge", interaction.guild.me, f"{len(deleted)} messages in {interaction.channel.mention}")
        except discord.Forbidden:
            embed = BotEmbed.error("Missing Permissions", "I need the **Manage Messages** permission to purge.")
        await interaction.followup.send(embed=embed, ephemeral=False)

    # ---------- Auto-unmute logging ----------
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.is_timed_out() and not after.is_timed_out():
            guild = after.guild
            # Try to find who removed it via audit log
            try:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                    if entry.target.id == after.id and entry.changes.before.timeout and entry.changes.after.timeout is None:
                        moderator = entry.user
                        reason = entry.reason or "Timeout expired"
                        await self._log(guild, moderator, "Auto‑Unmute", after, reason)
                        break
            except:
                pass


async def setup(bot):
    # Ensure mod_log_channel_id column exists in guild_settings
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("ALTER TABLE guild_settings ADD COLUMN mod_log_channel_id INTEGER DEFAULT 0")
            await db.commit()
        except:
            pass
    await bot.add_cog(Moderation(bot))