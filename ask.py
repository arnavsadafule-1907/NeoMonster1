import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import logging
import aiosqlite
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from formatter import BotEmbed

logger = logging.getLogger("discord.cogs.ask")

# ====================================================================
#  CONFIGURATION
# ====================================================================
MINECRAFT_SERVER_IP = os.getenv("MINECRAFT_SERVER_IP", "play.decaysmp.net")
SERVER_NAME = "DecaySMP"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
CACHE_TTL = 60  # seconds – how long to keep the knowledge cache

# ====================================================================
#  FAQ (quick keyword matches)
# ====================================================================
FAQ = [
    {
        "keywords": ["eye armor trim", "armor trim", "trim drop"],
        "answer": "**Eye Armor Trim** has a **1 in 200** chance to drop from custom loot chests.\nUse `/warp trims` in-game to find the location."
    },
    {
        "keywords": ["server rules", "rules"],
        "answer": "**DecaySMP Rules:**\n• No griefing\n• No hacking / cheat clients\n• Respect all players\nFull details in <#rules>."
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
    # Added whitelist FAQ for quick matches
    {
        "keywords": ["whitelist", "whitelisted", "how to join", "get whitelisted"],
        "answer": "To get whitelisted on DesireSMP, go to the <#1537475289834065941> channel and follow the instructions there. Staff will review your application."
    },
]

def make_embed(title: str, description: str, color: int, footer: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    return embed

class Ask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._knowledge_cache = None
        self._cache_timestamp = None

    async def _get_knowledge_from_db(self) -> str:
        """Fetch all knowledge entries from the database and format as text."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT section, content FROM knowledge_entries ORDER BY channel_id, id"
            )
            rows = await cursor.fetchall()

        if not rows:
            return "No knowledge available yet. Please ask staff."

        # Group by section (or use 'general' if None)
        sections = {}
        for row in rows:
            section = row["section"] or "general"
            sections.setdefault(section, []).append(row["content"])

        # Build the final text
        parts = []
        for section, contents in sections.items():
            parts.append(f"=== {section.upper()} ===\n" + "\n".join(contents))
        return "\n\n".join(parts)

    async def get_knowledge(self) -> str:
        """Return cached knowledge or fetch fresh."""
        now = datetime.utcnow()
        if self._knowledge_cache is None or self._cache_timestamp is None or (now - self._cache_timestamp).total_seconds() > CACHE_TTL:
            self._knowledge_cache = await self._get_knowledge_from_db()
            self._cache_timestamp = now
        return self._knowledge_cache

    @app_commands.command(name="ask", description="Ask a question about the Minecraft server")
    @app_commands.describe(question="Your question about the server")
    @app_commands.checks.cooldown(1, 5.0)
    async def ask_command(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)

        # 1) FAQ (instant)
        answer = self.search_faq(question)
        if answer:
            embed = make_embed(f"📖 {SERVER_NAME} Help", answer, 0x00BFFF)
            return await interaction.followup.send(embed=embed)

        # 2) Live server status
        if self.is_server_status_question(question):
            status_embed = await self.get_server_status_embed()
            if status_embed:
                return await interaction.followup.send(embed=status_embed)
            else:
                embed = make_embed("Server Offline", "Could not fetch live server status.", 0xFF0000)
                return await interaction.followup.send(embed=embed)

        # 3) AI – always try Gemini if possible
        if GEMINI_API_KEY:
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                knowledge = await self.get_knowledge()

                system_prompt = f"""
You are the official assistant for the Minecraft server "{SERVER_NAME}" (IP: {MINECRAFT_SERVER_IP}).

The following is the **complete server knowledge base** – rules, limits, custom features, economy, staff, etc.:

=== START KNOWLEDGE ===
{knowledge}
=== END KNOWLEDGE ===

**Instructions:**
- Answer the user's question **using only the knowledge above** if possible.
- If the question is about real‑time status (players online, etc.), tell the user to use `/ask players` or `/ask status`.
- If the question is **not covered** in the knowledge base, use your **general Minecraft knowledge** to answer, but clearly state that it's general knowledge.
- If you genuinely don't know, say: "I don't have that information yet. Please ask staff or check the #server-announcements channel."

Be concise, helpful, and friendly.
"""
                response = client.models.generate_content(
                    model="models/gemini-2.5-flash",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"{system_prompt}\n\nUser question: {question}")]
                        )
                    ]
                )

                ai_answer = response.text if response.text else "I don't have that information yet. Please ask staff or check the relevant channels."
                embed = make_embed("🤖 AI Answer", ai_answer, 0x9B59B6)
                await interaction.followup.send(embed=embed)
                return

            except Exception as e:
                logger.error(f"Gemini error: {e}")
                # fall through to a polite fallback

        # 4) Final fallback – polite and helpful
        embed = make_embed(
            "🔍 Couldn't Find an Answer",
            "I don't have that information yet. Please ask staff or check the relevant channels.\n\n"
            "If you think this question should be answered, staff can add it to the knowledge base.",
            0xFFA500
        )
        await interaction.followup.send(embed=embed)

    # ---------- Admin: Reload knowledge from DB ----------
    @app_commands.command(name="reloadknowledge", description="Force reload the server knowledge from Discord channels (admin only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reload_knowledge(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # Clear cache so next ask fetches fresh data
            self._knowledge_cache = None
            self._cache_timestamp = None
            # Also trigger an immediate refresh from the updater cog if available
            updater = self.bot.get_cog("KnowledgeUpdater")
            if updater:
                await updater.refresh_knowledge()
                embed = make_embed("✅ Knowledge Reloaded", "Server info has been refreshed from Discord channels.", 0x00FF00)
            else:
                embed = make_embed("⚠️ Partial Reload", "Cache cleared, but KnowledgeUpdater cog not found. Manual refresh may be needed.", 0xFFA500)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = make_embed("❌ Reload Failed", str(e), 0xFF0000)
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- Helper methods (unchanged) ----------
    def search_faq(self, question: str) -> str | None:
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

    async def get_server_status_embed(self) -> discord.Embed | None:
        try:
            from mcstatus import JavaServer
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

            embed = make_embed(f"🌐 {SERVER_NAME} Server Status", description, 0x00FF00)
            if motd:
                embed.add_field(name="MOTD", value=motd, inline=False)
            return embed

        except ImportError:
            logger.error("mcstatus not installed")
            return None
        except Exception as e:
            logger.error(f"Server status fetch failed: {e}")
            return None

async def setup(bot: commands.Bot):
    await bot.add_cog(Ask(bot))