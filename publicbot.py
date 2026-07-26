import discord
from discord import app_commands
from discord.ext import commands
from formatter import BotEmbed
import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class PublicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========== SERVER JOIN/LEAVE LOGS ==========
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Log to a private channel (replace with your own log channel ID)
        log_channel_id = await self.get_join_log_channel()
        if log_channel_id:
            channel = self.bot.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🟢 Joined New Server",
                    description=f"**{guild.name}**",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="Owner", value=f"{guild.owner} ({guild.owner_id})")
                embed.add_field(name="Members", value=guild.member_count)
                embed.add_field(name="Server ID", value=guild.id)
                embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                await channel.send(embed=embed)

        # Send welcome DM to server owner
        try:
            embed = BotEmbed.info(
                "🛡️ NeoMonster – Thank You for Choosing Us!",
                "Your server is now protected.\n\n"
                "**Quick Start:**\n"
                "• `/antinuke logchannel #logs` – Set security alerts\n"
                "• `/antinuke whitelist add @you` – Protect yourself\n"
                "• `/help` – See all commands\n\n"
                "**Need help?** Join our support server: https://discord.gg/c5Y79DA542"
            )
            await guild.owner.send(embed=embed)
        except:
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
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="Owner", value=f"{guild.owner} ({guild.owner_id})")
                embed.add_field(name="Members", value=guild.member_count)
                embed.add_field(name="Server ID", value=guild.id)
                await channel.send(embed=embed)

    async def get_join_log_channel(self):
        """Return your private log channel ID (hardcoded)."""
        # 🔁 REPLACE THIS WITH YOUR REAL CHANNEL ID
        return 123456789012345678

    # ========== VOTE COMMAND ==========
    @app_commands.command(name="vote", description="Vote for NeoMonster on top.gg")
    async def vote(self, interaction: discord.Interaction):
        embed = BotEmbed.info(
            "🗳️ Vote for NeoMonster",
            "Help us grow by voting!\n\n"
            "**[Vote on top.gg](https://top.gg/bot/YOUR_BOT_ID/vote)**\n"
            "Voting helps more servers discover our security bot."
        )
        await interaction.response.send_message(embed=embed)

    # ========== SUPPORT COMMAND ==========
    @app_commands.command(name="support", description="Get support for NeoMonster")
    async def support(self, interaction: discord.Interaction):
        embed = BotEmbed.info(
            "📞 NeoMonster Support",
            "**Need help?**\n\n"
            "• 📧 Email: contact@olympusbot.in\n"
            "• 🌐 Website: https://neomonster1-production.up.railway.app/\n"
            "• 📚 Documentation: `/help`\n"
            "• 🎫 Support Server: [Join](https://discord.gg/c5Y79DA542)\n\n"
            "Our team typically responds within 24 hours."
        )
        await interaction.response.send_message(embed=embed)

    # ========== INVITE COMMAND ==========
    @app_commands.command(name="invite", description="Get the invite link for NeoMonster")
    async def invite(self, interaction: discord.Interaction):
        invite_url = "https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473370870&integration_type=0&scope=bot+applications.commands"
        embed = BotEmbed.info(
            "🔗 Invite NeoMonster",
            f"**[Click here to invite me to your server]({invite_url})**\n\n"
            "Share this link with other server owners to help them stay protected!"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(PublicBot(bot))