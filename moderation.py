import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from checks import admin_only
from formatter import BotEmbed

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Helper to send log to serverlogger
    async def log_action(self, interaction, action, target, reason=""):
        logger_cog = self.bot.get_cog("ServerLogger")
        if logger_cog:
            await logger_cog.log_mod_action(interaction.guild, interaction.user, action, target, reason)

    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.describe(member="Member to ban", reason="Reason for ban")
    @admin_only()
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            embed = BotEmbed.error("Permission Denied", "You cannot ban this member.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await member.ban(reason=reason)
            embed = BotEmbed.success("Member Banned", f"{member.mention} has been banned.\n**Reason:** {reason}")
            await self.log_action(interaction, "ban", member, reason)
        except discord.Forbidden:
            embed = BotEmbed.error("Missing Permissions", "I don't have permission to ban this member. Check my role position and permissions.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @admin_only()
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            await member.kick(reason=reason)
            embed = BotEmbed.success("Member Kicked", f"{member.mention} has been kicked.\n**Reason:** {reason}")
            await self.log_action(interaction, "kick", member, reason)
        except discord.Forbidden:
            embed = BotEmbed.error("Missing Permissions", "I don't have permission to kick this member. Check my role position and permissions.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mute", description="Timeout a member")
    @app_commands.describe(member="Member to mute", duration="Duration in minutes", reason="Reason")
    @admin_only()
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        if member.is_timed_out():
            embed = BotEmbed.warning("Already Muted", f"{member.mention} is already muted.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            until = discord.utils.utcnow() + timedelta(minutes=duration)
            await member.timeout(until, reason=reason)
            embed = BotEmbed.success("Member Muted", f"{member.mention} has been muted for {duration} minutes.\n**Reason:** {reason}")
            await self.log_action(interaction, "mute", member, reason)
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I cannot mute this member. Ensure I have the **Moderate Members** permission and my role is above theirs.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unmute", description="Remove a timeout from a member")
    @app_commands.describe(member="Member to unmute")
    @admin_only()
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not member.is_timed_out():
            embed = BotEmbed.warning("Not Muted", f"{member.mention} is not currently timed out.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await member.timeout(None, reason="Unmute")
            embed = BotEmbed.success("Member Unmuted", f"{member.mention} has been unmuted.")
            await self.log_action(interaction, "unmute", member)
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I cannot unmute this member. Check my role position and permissions.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warn", description="Warn a member (log only)")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @admin_only()
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            await member.send(embed=BotEmbed.warning("You were warned", f"**Server:** {interaction.guild.name}\n**Reason:** {reason}"))
        except:
            pass
        embed = BotEmbed.success("Warning Issued", f"{member.mention} has been warned.\n**Reason:** {reason}")
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction, "warn", member, reason)

    @app_commands.command(name="purge", description="Delete a number of messages")
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @admin_only()
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            embed = BotEmbed.error("Invalid Amount", "Please enter a number between 1 and 100.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
            embed = BotEmbed.success("Messages Purged", f"Deleted {len(deleted)} messages.")
        except discord.Forbidden:
            embed = BotEmbed.error("Missing Permissions", "I need the **Manage Messages** permission to purge.")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))