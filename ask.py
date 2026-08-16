import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import logging
import re
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
CACHE_TTL = 60  # seconds

# ====================================================================
#  FAQ – Full Channel List + Common Questions
# ====================================================================
FAQ = [
    # ---- Server Info ----
    {
        "keywords": ["server ip", "what is the ip", "ip address", "connect", "join server", "server address"],
        "answer": f"**Server IP:** `{MINECRAFT_SERVER_IP}`\n**Version:** 1.21+"
    },
    {
        "keywords": ["server rules", "rules", "where are rules", "rule list", "server rule", "server rules list"],
        "answer": "📜 Server rules are in <#1534119515565326346>."
    },
    {
        "keywords": ["server updates", "updates", "latest news", "what's new", "server status", "status update", "news"],
        "answer": "📢 Server updates and status are posted in <#1537491924045529110> and <#1536210596222083082>."
    },
    {
        "keywords": ["server concept", "concept", "server ideas", "concepts", "server theme", "server concept channel"],
        "answer": "💡 Server concepts are discussed in <#1537491731593822290>."
    },

    # ---- Whitelist ----
    {
        "keywords": ["whitelist", "whitelisted", "how to join", "get whitelisted", "apply", "join server", "whitelist application", "apply for whitelist", "get added"],
        "answer": "🔐 To get whitelisted, go to <#1537475289834065941> and follow the instructions."
    },

    # ---- Custom Recipes ----
    {
        "keywords": ["custom recipes", "recipes", "crafting recipes", "recipe list", "how to craft", "where are recipes", "custom crafting", "server recipes"],
        "answer": "🧪 Custom recipes are listed in <#1537491780776361996>."
    },

    # ---- Server Kits ----
    {
        "keywords": ["kit", "kits", "starter kit", "server kit", "how to get kit", "kits command", "kit list", "free kit", "starting items"],
        "answer": "🎒 Server kits and item limits are in <#1525873414080823556>."
    },

    # ---- Polls & Events ----
    {
        "keywords": ["poll", "polls", "voting", "vote", "poll channel", "community vote", "server poll"],
        "answer": "📊 Polls and voting happen in <#1537491982044373013>."
    },
    {
        "keywords": ["events", "event", "server event", "upcoming event", "event schedule", "community event", "event calendar"],
        "answer": "🎉 Events are announced in <#1537491842591883426>."
    },

    # ---- Ranked SMP ----
    {
        "keywords": ["ranked smp", "ranked", "ranked plugin", "ranked info", "ranked server", "ranked mode", "competitive smp"],
        "answer": "🏆 Ranked SMP info is in <#1537796894867066980>."
    },

    # ---- Strength SMP ----
    {
        "keywords": ["strength smp", "strength", "strength plugin", "strength abilities", "strength s4", "strength server", "s4", "season 4"],
        "answer": "⚔️ Strength SMP info is in <#1537797210819792927> and abilities in <#1537799580190515291>."
    },

    # ---- Teams ----
    {
        "keywords": ["team register", "register team", "team", "teams", "team registration", "team signup", "create team"],
        "answer": "📋 Team registration is in <#1537846246629449809>."
    },

    # ---- Booster Perks ----
    {
        "keywords": ["booster", "boosters", "booster perks", "perks", "booster info", "boost", "server boost"],
        "answer": "🚀 Booster perks are listed in <#1534209707047129248>."
    },

    # ---- Punishments ----
    {
        "keywords": ["punishment", "punishments", "strikes", "ban", "how many strikes", "strike system", "ban rules", "punishment system"],
        "answer": "⚖️ Punishment system and strike info are in <#1530079728956866661>."
    },

    # ---- Tickets / Support ----
    {
        "keywords": ["ticket", "tickets", "support", "help", "report", "support ticket", "open ticket", "staff help"],
        "answer": "🎫 Support tickets are handled in <#1525874371695083671>."
    },

    # ---- Texture Pack ----
    {
        "keywords": ["texture pack", "resource pack", "pack", "download texture", "texture pack download", "server texture", "custom textures"],
        "answer": "🎨 The server texture pack is available in <#1537799391266476062>."
    },

    # ---- Existing FAQ entries ----
    {
        "keywords": ["eye armor trim", "armor trim", "trim drop", "eye trim", "armor trim drop"],
        "answer": "**Eye Armor Trim** has a **1 in 200** chance to drop from custom loot chests.\nUse `/warp trims` in-game to find the location."
    },
    {
        "keywords": ["discord", "support server", "discord link", "join discord", "discord invite"],
        "answer": "Join our Discord for support: https://discord.gg/desiresmp"
    },
    {
        "keywords": ["vote", "voting", "vote link", "voting site", "server vote"],
        "answer": "Vote for us to earn rewards: [Vote link](https://minecraft-server-list.com/)"
    },
]

# ====================================================================
#  Helper Functions
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
        self._knowledge_cache = None
        self._cache_timestamp = None

    # ---------- Knowledge DB loader ----------
    async def _get_knowledge_from_db(self) -> str:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT section, content FROM knowledge_entries ORDER BY channel_id, id"
            )
            rows = await cursor.fetchall()

        if not rows:
            return "No knowledge available yet. Please ask staff."

        sections = {}
        for row in rows:
            section = row["section"] or "general"
            sections.setdefault(section, []).append(row["content"])

        parts = []
        for section, contents in sections.items():
            parts.append(f"=== {section.upper()} ===\n" + "\n".join(contents))
        return "\n\n".join(parts)

    async def get_knowledge(self) -> str:
        now = datetime.utcnow()
        if self._knowledge_cache is None or self._cache_timestamp is None or (now - self._cache_timestamp).total_seconds() > CACHE_TTL:
            self._knowledge_cache = await self._get_knowledge_from_db()
            self._cache_timestamp = now
        return self._knowledge_cache

    # ---------- FAQ matcher (whole‑word only) ----------
    def search_faq(self, question: str) -> str | None:
        q = question.lower()
        for item in FAQ:
            for keyword in item["keywords"]:
                # Match whole word using regex word boundaries
                if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', q):
                    return item["answer"]
        return None

    # ---------- Server status check ----------
    def is_server_status_question(self, question: str) -> bool:
        q = question.lower()
        keywords = ["players", "online", "status", "version", "motd", "ping", "uptime", "server online", "is server up"]
        return any(re.search(r'\b' + re.escape(k) + r'\b', q) for k in keywords)

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

        # 1) FAQ (instant, whole‑word match)
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

        # 3) AI – Gemini fallback
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

        # 4) Final fallback – helpful message
        embed = make_embed(
            "🔍 Couldn't Find an Answer",
            "I don't have that information yet. Please ask staff or check the relevant channels.\n\n"
            "If you think this question should be answered, staff can add it to the knowledge base.",
            0xFFA500
        )
        await interaction.followup.send(embed=embed)

    # ---------- Admin: Reload knowledge ----------
    @app_commands.command(name="reloadknowledge", description="Force reload the server knowledge from Discord channels (admin only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reload_knowledge(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            self._knowledge_cache = None
            self._cache_timestamp = None
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Ask(bot))