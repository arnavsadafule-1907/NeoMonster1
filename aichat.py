import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
import aiosqlite
import re
import hashlib
from datetime import datetime, timedelta
import pytz
from openai import OpenAI
from formatter import BotEmbed

logger = logging.getLogger("discord.cogs.aichat")

# ====================================================================
#  CONFIGURATION
# ====================================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
COOLDOWN_SECONDS = 8
CACHE_TTL_SECONDS = 3600  # 1 hour

# DeepSeek endpoint
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ====================================================================
#  SAFETY / SYSTEM PROMPT
# ====================================================================
SYSTEM_PROMPT = """
You are a friendly, helpful AI assistant. You answer questions clearly and concisely.

**Rules you MUST follow:**
- Do NOT generate any 18+ or sexually explicit content.
- Do NOT generate any abusive, hateful, harassing, or toxic language.
- Do NOT generate any dangerous or illegal content.
- If you don't know something, say "I don't know" rather than guessing.
- If asked for a link, provide a safe, relevant link if it exists – otherwise say you don't have one.

Be conversational, engaging, and always respectful.
"""

# ====================================================================
#  HELPER
# ====================================================================
def make_embed(title: str, description: str, color: int, footer: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    return embed

class AIChat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldown = {}
        self._cache = {}  # question_hash -> (answer, timestamp)
        self._client = None
        if DEEPSEEK_API_KEY:
            self._client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL
            )
            logger.info("✅ DeepSeek client initialized.")
        else:
            logger.warning("⚠️ DEEPSEEK_API_KEY not set – AI will not work.")

    # ---------- Caching ----------
    def _get_cached_answer(self, question: str) -> str | None:
        h = hashlib.md5(question.lower().encode()).hexdigest()
        if h in self._cache:
            answer, ts = self._cache[h]
            if datetime.utcnow() - ts < timedelta(seconds=CACHE_TTL_SECONDS):
                return answer
            else:
                del self._cache[h]
        return None

    def _cache_answer(self, question: str, answer: str):
        h = hashlib.md5(question.lower().encode()).hexdigest()
        self._cache[h] = (answer, datetime.utcnow())

    # ---------- Local answers ----------
    def local_answer(self, question: str) -> str | None:
        q = question.lower()
        if re.search(r'\b(date|today|current date|what day|what is the date)\b', q):
            now = datetime.now(pytz.timezone("UTC"))
            return f"📅 Today is **{now.strftime('%B %d, %Y')}** (UTC)."
        if re.search(r'\b(time|current time|what time|now)\b', q):
            now = datetime.now(pytz.timezone("UTC"))
            return f"🕐 The current time is **{now.strftime('%H:%M:%S')}** (UTC)."
        return None

    # ---------- AI processor ----------
    async def process_question(self, message: discord.Message, question: str):
        user_id = message.author.id
        now = datetime.utcnow()

        # Cooldown
        if user_id in self._cooldown:
            last = self._cooldown[user_id]
            if (now - last).total_seconds() < COOLDOWN_SECONDS:
                embed = make_embed(
                    "⏳ Slow Down",
                    f"Please wait **{COOLDOWN_SECONDS} seconds** between questions.",
                    0xFFA500
                )
                await message.reply(embed=embed, mention_author=True, delete_after=5)
                return
        self._cooldown[user_id] = now

        # Local answer
        local = self.local_answer(question)
        if local:
            embed = make_embed("📋 Real‑Time Answer", local, 0x00BFFF)
            await message.reply(embed=embed, mention_author=True)
            return

        # Check cache
        cached = self._get_cached_answer(question)
        if cached:
            embed = make_embed("🤖 AI Answer (cached)", cached, 0x9B59B6)
            await message.reply(embed=embed, mention_author=True)
            return

        await message.channel.typing()

        if not self._client:
            embed = make_embed(
                "❌ AI Not Configured",
                "The DeepSeek API key is missing. Please ask an admin to set it up.",
                0xFFA500
            )
            await message.reply(embed=embed, mention_author=True)
            return

        try:
            # DeepSeek API call (OpenAI-compatible)
            response = self._client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                max_tokens=1500,
                temperature=0.7
            )

            ai_answer = response.choices[0].message.content
            if not ai_answer:
                embed = make_embed("❌ No Response", "I couldn't generate a response. Please try again.", 0xFFA500)
                await message.reply(embed=embed, mention_author=True)
                return

            self._cache_answer(question, ai_answer)
            embed = make_embed("🤖 AI Answer", ai_answer, 0x9B59B6)
            await message.reply(embed=embed, mention_author=True)

        except Exception as e:
            logger.error(f"DeepSeek error: {e}")
            embed = make_embed(
                "❌ AI Error",
                f"The AI service is currently unavailable.\n**Error:** `{str(e)[:150]}`",
                0xFF0000
            )
            await message.reply(embed=embed, mention_author=True)

    # ---------- on_message ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ai_channel_id = await self.get_ai_channel(message.guild.id)
        if not ai_channel_id or message.channel.id != ai_channel_id:
            return
        if message.content.startswith('/'):
            return
        await self.process_question(message, message.content)

    # ---------- Database helpers ----------
    async def get_ai_channel(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT channel_id FROM ai_channels WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_ai_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO ai_channels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
            await db.commit()

    async def remove_ai_channel(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM ai_channels WHERE guild_id = ?", (guild_id,))
            await db.commit()

    # ---------- Slash commands ----------
    @app_commands.command(name="setaichannel", description="Set the AI chat channel (admin only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.set_ai_channel(interaction.guild_id, channel.id)
        embed = make_embed("✅ AI Channel Set", f"The AI will now respond in {channel.mention}.", 0x00FF00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="removeaichannel", description="Remove the AI channel setting (admin only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction: discord.Interaction):
        await self.remove_ai_channel(interaction.guild_id)
        embed = make_embed("✅ AI Channel Removed", "The AI will no longer respond to messages.", 0x00FF00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
        """)
        await db.commit()
    await bot.add_cog(AIChat(bot))