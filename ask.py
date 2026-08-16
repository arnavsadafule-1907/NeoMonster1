import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import logging
from typing import Optional

# Setup logger
logger = logging.getLogger("discord.cogs.ask")

# ====================================================================
#  CONFIGURATION – edit these values
# ====================================================================
MINECRAFT_SERVER_IP = os.getenv("MINECRAFT_SERVER_IP", "play.decaysmp.net")
SERVER_NAME = "DecaySMP"

# Simple FAQ knowledge base (keywords -> answer)
FAQ = [
    {
        "keywords": ["eye armor trim", "armor trim", "trim drop"],
        "answer": (
            "**Eye Armor Trim** has a **1 in 200** chance to drop from custom loot chests.\n"
            "Use `/warp trims` in-game to find the location."
        )
    },
    {
        "keywords": ["server rules", "rules"],
        "answer": (
            "**DecaySMP Rules:**\n"
            "• No griefing\n"
            "• No hacking / cheat clients\n"
            "• Respect all players\n"
            "Full details in <#rules>."
        )
    },
    {
        "keywords": ["ip", "address", "connect"],
        "answer": f"**Server IP:** `{MINECRAFT_SERVER_IP}`\n**Version:** 1.21+"
    },
    {
        "keywords": ["discord", "support"],
        "answer": "Join our Discord for support: https://discord.gg/desiresmp"
    },
    {
        "keywords": ["vote", "voting"],
        "answer": "Vote for us to earn rewards: [Vote link](https://minecraft-server-list.com/)"
    },
]

# ====================================================================
#  Helper function to create Embeds (replaces BotEmbed)
# ====================================================================
def make_embed(title: str, description: str, color: int, footer: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    return embed

# ====================================================================
#  Cog
# ====================================================================
class Ask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Ask a question about the Minecraft server")
    @app_commands.describe(question="Your question about the server")
    @app_commands.checks.cooldown(1, 5.0)  # Prevents spam: 1 use per 5 seconds
    async def ask_command(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)

        # 1) Try to answer from FAQ
        answer = self.search_faq(question)
        if answer:
            embed = make_embed(f"📖 {SERVER_NAME} Help", answer, 0x00BFFF)  # Cyan
            return await interaction.followup.send(embed=embed)

        # 2) Check for live server info keywords
        if self.is_server_status_question(question):
            status_embed = await self.get_server_status_embed()
            if status_embed:
                return await interaction.followup.send(embed=status_embed)
            else:
                embed = make_embed(
                    "Server Offline", 
                    "Could not fetch live server status. The server may be offline.", 
                    0xFF0000  # Red
                )
                return await interaction.followup.send(embed=embed)

        # 3) No answer found
        embed = make_embed(
            "Unknown Question",
            "I couldn't find an answer. Please ask staff or rephrase your question.",
            0xFFA500  # Orange
        )
        await interaction.followup.send(embed=embed)

    def search_faq(self, question: str) -> Optional[str]:
        q = question.lower()
        for item in FAQ:
            for keyword in item["keywords"]:
                if keyword in q:
                    return item["answer"]
        return None

    def is_server_status_question(self, question: str) -> bool:
        q = question.lower()
        keywords = ["players", "online", "status", "ip", "version", "motd", "ping"]
        return any(k in q for k in keywords)

    async def get_server_status_embed(self) -> Optional[discord.Embed]:
        """Fetch live server status using mcstatus without blocking the bot."""
        try:
            from mcstatus import JavaServer

            # --- FIX: Run the blocking .status() in a background thread ---
            server = JavaServer.lookup(MINECRAFT_SERVER_IP)
            status = await asyncio.to_thread(server.status)

            player_online = status.players.online
            player_max = status.players.max
            version = status.version.name
            motd = str(status.description).replace("§", "")
            latency = getattr(status, 'latency', None)

            description = (
                f"**Status:** 🟢 Online\n"
                f"**Players:** {player_online}/{player_max}\n"
                f"**Version:** {version}\n"
                f"**Ping:** {latency}ms" if latency else ""
            )

            embed = make_embed(f"🌐 {SERVER_NAME} Server Status", description, 0x00FF00)  # Green
            if motd:
                embed.add_field(name="MOTD", value=motd, inline=False)
            
            return embed

        except ImportError:
            logger.error("mcstatus library not installed. Please run: pip install mcstatus")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch server status: {e}")
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{self.__class__.__name__} cog loaded!")

async def setup(bot: commands.Bot):
    await bot.add_cog(Ask(bot))