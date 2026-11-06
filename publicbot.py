import discord
from discord import app_commands
from discord.ext import commands
from formatter import BotEmbed
import os
from datetime import datetime, timezone

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class PublicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log_channel_id = await self.get_join_log_channel()
        if log_channel_id:
            channel = self.bot.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🟢 Joined New Server",
                    description=f"**{guild.name}**",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Owner", value=f"{guild.owner} ({guild.owner_id})")
                embed.add_field(name="Members", value=str(guild.member_count or 0))
                embed.add_field(name="Server ID", value=str(guild.id))
                embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        log_channel_id = await self.get_join_log_channel()
        if log_channel_id:
            channel = self.bot.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🔴 Left Server",
                    description=f"**{guild.name}**",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Owner", value=f"{guild.owner} ({guild.owner_id})")
                embed.add_field(name="Members", value=str(guild.member_count or 0))
                embed.add_field(name="Server ID", value=str(guild.id))
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    async def get_join_log_channel(self):
        ch_id = os.getenv("JOIN_LOG_CHANNEL_ID")
        if ch_id and ch_id.strip().isdigit():
            return int(ch_id.strip())
        return None

    @app_commands.command(name="support", description="Get support for NeoMonster")
    async def support(self, interaction: discord.Interaction):
        embed = BotEmbed.info(
            "📞 NeoMonster Support",
            "**Need help?**\n\n"
            "• 📧 Email: contact@olympusbot.in\n"
            "• 🌐 Website: https://neomonster1.onrender.com\n"
            "• 📚 Documentation: `/help`\n"
            "• 🎫 Support Server: [Join](https://discord.gg/f8zTc4tmHx)\n\n"
            "Our team typically responds within 24 hours."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite", description="Get the invite link for NeoMonster")
    async def invite(self, interaction: discord.Interaction):
        bot_id = self.bot.user.id if self.bot.user else "1528368412093579376"
        invite_url = f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions=1100473370870&integration_type=0&scope=bot+applications.commands"
        embed = BotEmbed.info(
            "🔗 Invite NeoMonster",
            f"**[Click here to invite me to your server]({invite_url})**\n\n"
            "Share this link with other server owners to help them stay protected!"
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(PublicBot(bot))
