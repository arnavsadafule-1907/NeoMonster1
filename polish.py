import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import platform
import psutil
from datetime import datetime
from formatter import BotEmbed

START_TIME = datetime.utcnow()

class Polish(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_rotation.start()

    def cog_unload(self):
        self.status_rotation.cancel()

    @tasks.loop(minutes=5)
    async def status_rotation(self):
        statuses = [
            discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.bot.guilds)} servers | /help"),
            discord.Activity(type=discord.ActivityType.watching, name="for raids | 24/7 Protection"),
            discord.Activity(type=discord.ActivityType.watching, name="over your security"),
        ]
        for status in statuses:
            await self.bot.change_presence(activity=status)
            # No sleep needed – status changes on each loop iteration

    @status_rotation.before_loop
    async def before_status(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Send a professional welcome DM to the server owner
        try:
            embed = discord.Embed(
                title="🛡️ DesireSmpYou for Choosing Us!",
                description=(
                    "Your server is now protected by the most advanced Discord security bot.\n\n"
                    "**Quick Setup:**\n"
                    "• `/antinuke logchannel #logs` – Set security alert channel\n"
                    "• `/antinuke whitelist add @you` – Whitelist yourself\n"
                    "• `/help` – View all commands\n\n"
                    "**Links:**\n"
                    f"• Invite: https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands\n"
                    "• Website: https://DesireSmp1-production.up.railway.app/"

                ),
                color=discord.Color.green()
            )
            await guild.owner.send(embed=embed)
        except:
            pass

    @app_commands.command(name="botinfo", description="Show detailed bot information")
    async def botinfo(self, interaction: discord.Interaction):
        uptime = datetime.utcnow() - START_TIME
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed = BotEmbed.info("DesireSmp Bot Information")
        embed.add_field(name="🤖 Bot Name", value=self.bot.user.name, inline=True)
        embed.add_field(name="🆔 Bot ID", value=self.bot.user.id, inline=True)
        embed.add_field(name="📅 Created", value=self.bot.user.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"{hours}h {minutes}m {seconds}s", inline=True)
        embed.add_field(name="🌐 Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="👥 Users", value=sum(g.member_count for g in self.bot.guilds), inline=True)
        embed.add_field(name="💾 Memory", value=f"{psutil.Process().memory_info().rss / 1024**2:.1f} MB", inline=True)
        embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
        embed.add_field(name="📊 Commands", value="65+", inline=True)
        embed.add_field(name="💿 OS", value=platform.system(), inline=True)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Polish(bot))