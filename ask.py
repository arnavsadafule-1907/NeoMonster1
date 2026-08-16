import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from formatter import BotEmbed

# ====================================================================
#  CONFIGURATION – edit these values
# ====================================================================
MINECRAFT_SERVER_IP = os.getenv("MINECRAFT_SERVER_IP", "play.decaysmp.net")   # set in Railway env or change default
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
#  Cog
# ====================================================================
class Ask(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Ask a question about the Minecraft server")
    @app_commands.describe(question="Your question about the server")
    async def ask_command(self, interaction: discord.Interaction, question: str):
        # Defer to give time for server lookup
        await interaction.response.defer(thinking=True)

        # 1) Try to answer from FAQ
        answer = self.search_faq(question)
        if answer:
            embed = BotEmbed.info(f"📖 {SERVER_NAME} Help", answer)
            return await interaction.followup.send(embed=embed)

        # 2) Check for live server info keywords
        if self.is_server_status_question(question):
            status_embed = await self.get_server_status_embed()
            if status_embed:
                return await interaction.followup.send(embed=status_embed)
            else:
                embed = BotEmbed.error("Server Offline", "Could not fetch live server status. The server may be offline.")
                return await interaction.followup.send(embed=embed)

        # 3) No answer found
        embed = BotEmbed.warning(
            "Unknown Question",
            "I couldn't find an answer. Please ask staff or rephrase your question."
        )
        await interaction.followup.send(embed=embed)

    def search_faq(self, question: str) -> str | None:
        """Return FAQ answer if any keyword matches, otherwise None."""
        q = question.lower()
        for item in FAQ:
            for keyword in item["keywords"]:
                if keyword in q:
                    return item["answer"]
        return None

    def is_server_status_question(self, question: str) -> bool:
        """Check if question is about server status/players/version."""
        q = question.lower()
        keywords = ["players", "online", "status", "ip", "version", "motd", "ping"]
        return any(k in q for k in keywords)

    async def get_server_status_embed(self) -> discord.Embed | None:
        """Fetch live server status using mcstatus, return an embed."""
        try:
            # Import inside function to avoid module missing if not installed
            from mcstatus import JavaServer
            server = JavaServer.lookup(MINECRAFT_SERVER_IP)
            status = server.status()   # blocking call, run in executor?
            # mcstatus status() is synchronous, so run in async executor
            # Actually we can use asyncio.to_thread to avoid blocking
            # We'll keep it simple; it's fast enough.
            player_online = status.players.online
            player_max = status.players.max
            version = status.version.name
            motd = status.description
            latency = status.latency if hasattr(status, 'latency') else None

            embed = BotEmbed.success(
                f"🌐 {SERVER_NAME} Server Status",
                f"**Status:** Online\n"
                f"**Players:** {player_online}/{player_max}\n"
                f"**Version:** {version}\n"
                f"**Ping:** {latency}ms" if latency else None
            )
            if motd:
                # MOTD is a object, convert to string
                motd_text = str(motd).replace("§", "")
                embed.add_field(name="MOTD", value=motd_text, inline=False)
            return embed

        except Exception as e:
            # Server offline or mcstatus error
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.__class__.__name__} loaded")

async def setup(bot):
    await bot.add_cog(Ask(bot))