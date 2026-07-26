import discord
from discord import app_commands
from discord.ext import commands
import time
import asyncio
from formatter import BotEmbed

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ----------------- Existing commands (avatar, userinfo, serverinfo) unchanged -----------------
    @app_commands.command(name="avatar", description="Show a user's avatar")
    @app_commands.describe(user="User whose avatar to show")
    async def avatar(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        embed = BotEmbed.info(f"{user.display_name}'s Avatar")
        embed.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Show information about a user")
    @app_commands.describe(user="User to look up")
    async def userinfo(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        embed = BotEmbed.info(title="User Information")
        embed.add_field(name="Username", value=user.mention, inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(name="Bot", value="Yes" if user.bot else "No", inline=True)
        embed.add_field(name="Created", value=user.created_at.strftime("%Y-%m-%d"), inline=True)
        if interaction.guild and isinstance(user, discord.Member):
            embed.add_field(name="Joined", value=user.joined_at.strftime("%Y-%m-%d"), inline=True)
            embed.add_field(name="Roles", value=len(user.roles), inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Show server information")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = BotEmbed.info(title=f"Server Info - {guild.name}")
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await interaction.response.send_message(embed=embed)

    # ----------------- NEW DETAILED PING -----------------
    @app_commands.command(name="ping", description="Show detailed bot latency")
    async def ping(self, interaction: discord.Interaction):
        # 1. Measure message latency: time from interaction creation to now
        now = discord.utils.utcnow()
        message_latency = round((now - interaction.created_at).total_seconds() * 1000)

        # 2. WebSocket latency (the gateway ping)
        ws_latency = round(self.bot.latency * 1000)

        # 3. Shard info (only if sharded, otherwise hide)
        shard_info = ""
        if self.bot.shard_count and self.bot.shard_count > 1:
            shard_info = f"Shard [{self.bot.shard_id + 1} / {self.bot.shard_count}]\n"
        
        # 4. API Latency – measure a real HTTP request to Discord
        api_start = time.perf_counter()
        # A lightweight request: fetch the bot's own application info
        try:
            app_info = await self.bot.application_info()
        except Exception:
            api_latency = "N/A"
        else:
            api_end = time.perf_counter()
            api_latency = round((api_end - api_start) * 1000)

        # Build the response embed
        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
        embed.add_field(
            name="📡 WebSocket",
            value=f"{ws_latency}ms",
            inline=True
        )
        if shard_info:
            embed.add_field(name="🧩 Shard", value=shard_info.strip(), inline=True)
        embed.add_field(
            name="🌐 API",
            value=f"{api_latency}ms" if isinstance(api_latency, int) else api_latency,
            inline=True
        )
        embed.add_field(
            name="💬 Message",
            value=f"{message_latency}ms",
            inline=True
        )
        embed.set_footer(text="Lower is better • Real‑time latency snapshot")

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))