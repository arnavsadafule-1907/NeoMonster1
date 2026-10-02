import discord
from discord import app_commands
from discord.ext import commands
import platform
import psutil
from datetime import datetime, timezone
from formatter import BotEmbed

START_TIME = datetime.now(timezone.utc)


class ServerStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="serverstatus", description="Show live bot status and Discord server information")
    async def serverstatus(self, interaction: discord.Interaction):
        guild = interaction.guild
        bot = self.bot

        uptime_delta = datetime.now(timezone.utc) - START_TIME
        total_seconds = int(uptime_delta.total_seconds())
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        ws_latency = round(bot.latency * 1000)
        try:
            memory_mb = psutil.Process().memory_info().rss / 1024 ** 2
            memory_str = f"{memory_mb:.1f} MB"
        except Exception:
            memory_str = "N/A"

        total_members = sum(g.member_count or 0 for g in bot.guilds)

        embed = discord.Embed(
            title="🛡️ NeoMonster – Live Status",
            color=0x3B82F6,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)

        embed.add_field(
            name="🤖 Bot",
            value=(
                f"**Online:** Yes\n"
                f"**Ping:** `{ws_latency}ms`\n"
                f"**Uptime:** `{uptime_str}`\n"
                f"**Memory:** `{memory_str}`\n"
                f"**Python:** `{platform.python_version()}`"
            ),
            inline=True
        )
        embed.add_field(
            name="🌐 Global",
            value=(
                f"**Guilds:** `{len(bot.guilds)}`\n"
                f"**Users:** `{total_members:,}`\n"
                f"**Commands:** `100+`\n"
                f"**Version:** `2.0.0`"
            ),
            inline=True
        )

        if guild:
            owner = guild.owner.mention if guild.owner else "Unknown"
            created = guild.created_at.strftime("%Y-%m-%d")
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            boost_tier = guild.premium_tier
            boost_count = guild.premium_subscription_count or 0

            embed.add_field(
                name="🏠 This Server",
                value=(
                    f"**Name:** {guild.name}\n"
                    f"**Owner:** {owner}\n"
                    f"**Created:** `{created}`\n"
                    f"**Members:** `{guild.member_count:,}`\n"
                    f"**Boost Tier:** `{boost_tier}` ({boost_count} boosts)"
                ),
                inline=False
            )
            embed.add_field(
                name="📊 Channels & Roles",
                value=(
                    f"**Text:** `{text_channels}` • "
                    f"**Voice:** `{voice_channels}` • "
                    f"**Categories:** `{categories}`\n"
                    f"**Roles:** `{len(guild.roles)}` • "
                    f"**Emojis:** `{len(guild.emojis)}`"
                ),
                inline=False
            )

        embed.set_footer(text="NeoMonster • Live status snapshot")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ServerStatus(bot))