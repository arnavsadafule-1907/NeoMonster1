import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

DEFAULT_RESPONSES = {
    "hello": "Hello! How can I help you?",
    "hi": "Hi there! 👋",
    "help": "Use `/help` to see all commands.",
    "invite": "You can invite me using the link in my profile!",
    "dashboard": "Our admin dashboard is private. Ask a staff member for access.",
    "rules": "Please check the #rules channel for server rules.",
    "apply": "To apply for staff, wait for application openings.",
    "ip": "This server doesn't have a game IP. This is a Discord community.",
}

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.responses = DEFAULT_RESPONSES.copy()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        # Check if the bot is mentioned
        if self.bot.user in message.mentions:
            content = message.content.replace(f"<@{self.bot.user.id}>", "").strip().lower()
            for trigger, response in self.responses.items():
                if trigger in content:
                    await message.channel.send(response)
                    return

    @app_commands.command(name="addresponse", description="Add an auto‑response")
    @app_commands.describe(trigger="Phrase to watch for", response="Bot's reply")
    @admin_only()
    async def add_response(self, interaction: discord.Interaction, trigger: str, response: str):
        self.responses[trigger.lower()] = response
        embed = BotEmbed.success("Response Added", f"When someone mentions me with `{trigger}`, I'll respond.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="removeresponse", description="Remove an auto‑response")
    @app_commands.describe(trigger="Trigger phrase to remove")
    @admin_only()
    async def remove_response(self, interaction: discord.Interaction, trigger: str):
        if trigger.lower() in self.responses and trigger.lower() not in DEFAULT_RESPONSES:
            del self.responses[trigger.lower()]
            embed = BotEmbed.success("Response Removed", f"Removed response for `{trigger}`.")
        else:
            embed = BotEmbed.error("Cannot Remove", "Default responses cannot be removed, or trigger not found.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chatbot(bot))