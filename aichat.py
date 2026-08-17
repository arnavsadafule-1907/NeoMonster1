import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
import aiosqlite
from datetime import datetime, timedelta
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

# ====================================================================
#  Safety Settings – blocks harmful content
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
#  Helper
# ====================================================================
def make_embed(title: str, description: str, color: int, footer: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    return embed

class AIChat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldown = {}  # user_id -> last_used_timestamp

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

    # ---------- Safe AI processor ----------
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

        # AI – Gemini with safety filters
        if GEMINI_API_KEY:
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)

                system_prompt = """
You are a friendly, helpful AI assistant. You answer questions clearly and concisely.

**Rules you MUST follow:**
- Do NOT generate any 18+ or sexually explicit content.
- Do NOT generate any abusive, hateful, harassing, or toxic language.
- Do NOT generate any dangerous or illegal content.
- If you don't know something, say "I don't know" rather than guessing.
- If asked for a link, provide a safe, relevant link if it exists – otherwise say you don't have one.

Be conversational, engaging, and always respectful.
"""
                response = client.models.generate_content(
                    model="models/gemini-2.5-flash",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"{system_prompt}\n\nUser question: {question}")]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        safety_settings=SAFETY_SETTINGS
                    )
                )

                # Check if response was blocked
                if not response.text:
                    # Check if it was blocked due to safety
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        embed = make_embed(
                            "🚫 Blocked",
                            "Your question was blocked because it may contain inappropriate content.",
                            0xFF0000
                        )
                        await message.reply(embed=embed, mention_author=True)
                        return
                    else:
                        embed = make_embed(
                            "❌ No Response",
                            "I couldn't generate a response. Please try again.",
                            0xFFA500
                        )
                        await message.reply(embed=embed, mention_author=True)
                        return

                # Post‑generation safety check (extra layer)
                ai_answer = response.text
                # Simple filter for obvious bad words (optional, but Gemini's safety handles most)
                # We'll just trust Gemini's safety settings.

                embed = make_embed("🤖 AI Answer", ai_answer, 0x9B59B6)
                await message.reply(embed=embed, mention_author=True)
                return

            except Exception as e:
                logger.error(f"Gemini error: {e}")
                embed = make_embed(
                    "❌ AI Error",
                    "The AI service is currently unavailable. Please try again later.",
                    0xFF0000
                )
                await message.reply(embed=embed, mention_author=True)
                return

        # Fallback if no API key
        embed = make_embed(
            "⚠️ AI Not Configured",
            "The Gemini API key is missing. Please ask an admin to set it up.",
            0xFFA500
        )
        await message.reply(embed=embed, mention_author=True)

    # ---------- on_message listener ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        ai_channel_id = await self.get_ai_channel(message.guild.id)
        if not ai_channel_id or message.channel.id != ai_channel_id:
            return

        # Ignore messages that start with a command prefix (optional)
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

    # ---------- Error handling for commands ----------
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            embed = make_embed("⛔ Permission Denied", "You need `Manage Server` permission to use this command.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    # Ensure the ai_channels table exists
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
        """)
        await db.commit()
    await bot.add_cog(AIChat(bot))