import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
import aiosqlite
import re
from datetime import datetime, timedelta
import pytz
from google import genai
from google.genai import types
from formatter import BotEmbed

logger = logging.getLogger("discord.cogs.aichat")

# ====================================================================
#  CONFIGURATION
# ====================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
COOLDOWN_SECONDS = 5
TIMEZONE = pytz.timezone("UTC")  # change to your local timezone

# ====================================================================
#  SAFETY SETTINGS
# ====================================================================
SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
]

# ====================================================================
#  MODEL FALLBACK LIST
# ====================================================================
MODEL_NAMES = [
    "models/gemini-3.6-flash",
    "models/gemini-2.5-flash",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-pro",
    "models/gemini-pro",
]

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
        self._active_model = None

    # ---------- Database helpers ----------
    async def get_ai_channel(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT channel_id FROM ai_channels WHERE guild_id = ?", (guild_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_ai_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ai_channels (guild_id, channel_id) VALUES (?, ?)",
                (guild_id, channel_id)
            )
            await db.commit()

    async def remove_ai_channel(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM ai_channels WHERE guild_id = ?", (guild_id,))
            await db.commit()

    # ---------- Local real‑time answers ----------
    def local_answer(self, question: str) -> str | None:
        q = question.lower()
        if re.search(r'\b(date|today|current date|what day|what is the date|todays date)\b', q):
            now = datetime.now(TIMEZONE)
            return f"📅 Today is **{now.strftime('%B %d, %Y')}** ({TIMEZONE.zone})."
        if re.search(r'\b(time|current time|what time|the time|now)\b', q):
            now = datetime.now(TIMEZONE)
            return f"🕐 The current time is **{now.strftime('%H:%M:%S')}** ({TIMEZONE.zone})."
        if re.search(r'\b(day of week|what day is it|weekday)\b', q):
            now = datetime.now(TIMEZONE)
            return f"📆 Today is **{now.strftime('%A')}**."
        return None

    # ---------- Find a working model ----------
    async def get_working_model(self, client):
        if self._active_model:
            return self._active_model

        for model_name in MODEL_NAMES:
            try:
                test = client.models.generate_content(
                    model=model_name,
                    contents=["Say hello"]
                )
                if test.text:
                    self._active_model = model_name
                    logger.info(f"✅ AI model active: {model_name}")
                    return model_name
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
                continue

        return None

    # ---------- AI processor with live search ----------
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

        # Local answers (date/time)
        local = self.local_answer(question)
        if local:
            embed = make_embed("📋 Real‑Time Answer", local, 0x00BFFF)
            await message.reply(embed=embed, mention_author=True)
            return

        # Typing indicator
        await message.channel.typing()

        # AI – Gemini with Google Search grounding
        if not GEMINI_API_KEY:
            embed = make_embed(
                "⚠️ AI Not Configured",
                "The Gemini API key is missing. Please ask an admin to set it up.",
                0xFFA500
            )
            await message.reply(embed=embed, mention_author=True)
            return

        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            model_name = await self.get_working_model(client)
            if not model_name:
                embed = make_embed(
                    "❌ AI Unavailable",
                    "No working Gemini model found. Please contact an admin.",
                    0xFF0000
                )
                await message.reply(embed=embed, mention_author=True)
                return

            system_prompt = """
You are a friendly, helpful AI assistant. You answer questions clearly and concisely.

**Rules you MUST follow:**
- Do NOT generate any 18+ or sexually explicit content.
- Do NOT generate any abusive, hateful, harassing, or toxic language.
- Do NOT generate any dangerous or illegal content.
- If you don't know something, say "I don't know" rather than guessing.
- If asked for a link, provide a safe, relevant link if it exists – otherwise say you don't have one.

**Important:** You have access to Google Search. Use it to fetch **real‑time, up‑to‑date information** whenever the user asks about current events, sports scores, weather, news, stocks, or any time‑sensitive topic. If the question is general knowledge, you can answer from your training data.

Be conversational, engaging, and always respectful.
"""
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=f"{system_prompt}\n\nUser question: {question}")]
                    )
                ],
                config=types.GenerateContentConfig(
                    safety_settings=SAFETY_SETTINGS,
                    tools=[types.Tool(google_search=types.GoogleSearch())]  # 🔥 LIVE SEARCH
                )
            )

            if not response.text:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    embed = make_embed(
                        "🚫 Blocked",
                        "Your question was blocked because it may contain inappropriate content.",
                        0xFF0000
                    )
                else:
                    embed = make_embed(
                        "❌ No Response",
                        "I couldn't generate a response. Please try again.",
                        0xFFA500
                    )
                await message.reply(embed=embed, mention_author=True)
                return

            # Include the search source if available (optional)
            answer = response.text
            if response.candidates and response.candidates[0].grounding_metadata:
                sources = response.candidates[0].grounding_metadata.web_search_queries
                if sources:
                    answer += f"\n\n🔍 *Sources: {', '.join(sources[:2])}*"

            embed = make_embed("🤖 AI Answer", answer, 0x9B59B6)
            await message.reply(embed=embed, mention_author=True)

        except Exception as e:
            logger.error(f"Gemini error: {e}")
            embed = make_embed(
                "❌ AI Error",
                "The AI service is currently unavailable. Please try again later.",
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

    # ---------- Slash commands ----------
    @app_commands.command(name="setaichannel", description="Set the AI chat channel (admin only)")
    @app_commands.describe(channel="The channel where AI will respond")
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

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            embed = make_embed("⛔ Permission Denied", "You need `Manage Server` permission to use this command.", 0xFF0000)
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