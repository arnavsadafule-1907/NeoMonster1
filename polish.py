import discord
from discord import app_commands
from discord.ext import commands, tasks
import platform
import psutil
from datetime import datetime, timezone
from formatter import BotEmbed

START_TIME = datetime.now(timezone.utc)

class Polish(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._status_index = 0
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
        status = statuses[self._status_index % len(statuses)]
        self._status_index += 1
        await self.bot.change_presence(activity=status)

    @status_rotation.before_loop
    async def before_status(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if not guild.owner:
            return
        try:
            bot_user_id = self.bot.user.id if self.bot.user else "me"
            embed = discord.Embed(
                title="🛡️ NeoMonster – Thank You for Choosing Us!",
                description=(
                    "Your server is now protected by the most advanced Discord security bot.\n\n"
                    "**Quick Setup:**\n"
                    "• `/antinuke logchannel #logs` – Set security alert channel\n"
                    "• `/antinuke whitelist add @you` – Whitelist yourself\n"
                    "• `/help` – View all commands\n\n"
                    "**Links:**\n"
                    f"• Invite: https://discord.com/oauth2/authorize?client_id={bot_user_id}&permissions=8&scope=bot%20applications.commands\n"
                    "• Website: https://neomonster1.onrender.com"
                ),
                color=discord.Color.green()
            )
            await guild.owner.send(embed=embed)
        except Exception:
            pass

    @app_commands.command(name="botinfo", description="Show detailed bot information")
    async def botinfo(self, interaction: discord.Interaction):
        uptime = datetime.now(timezone.utc) - START_TIME
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed = BotEmbed.info("NeoMonster Bot Information")
        embed.add_field(name="🤖 Bot Name", value=self.bot.user.name if self.bot.user else "NeoMonster", inline=True)
        embed.add_field(name="🆔 Bot ID", value=str(self.bot.user.id if self.bot.user else "N/A"), inline=True)
        created_str = self.bot.user.created_at.strftime("%Y-%m-%d") if self.bot.user else "N/A"
        embed.add_field(name="📅 Created", value=created_str, inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"{hours}h {minutes}m {seconds}s", inline=True)
        embed.add_field(name="🌐 Servers", value=str(len(self.bot.guilds)), inline=True)
        total_members = sum((g.member_count or 0) for g in self.bot.guilds)
        embed.add_field(name="👥 Users", value=str(total_members), inline=True)
        embed.add_field(name="💾 Memory", value=f"{psutil.Process().memory_info().rss / 1024**2:.1f} MB", inline=True)
        embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
        embed.add_field(name="📊 Commands", value="100+", inline=True)
        embed.add_field(name="💿 OS", value=platform.system(), inline=True)
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Polish(bot))
