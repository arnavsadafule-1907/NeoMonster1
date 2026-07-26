import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from logger import setup_logging
from db import init_db
from dashboard import app          # Flask app for dashboard
from threading import Thread       # to run Flask in background
from formatter import BotEmbed     # professional embed factory

load_dotenv()
logger = setup_logging()

class SecurityBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.bans = True
        super().__init__(command_prefix="/", intents=intents)
        self.owner_ids = set(map(int, os.getenv("OWNER_IDS", "").split(",")))

    async def setup_hook(self):
        # 1. Create database directory and tables FIRST
        await init_db()
        logger.info("Database ready")

        # 2. Now load all cogs (they can safely connect to the existing database)
        cogs = [
            "antinuke", "config", "recovery", "help",
            "moderation", "utility", "automod", "welcoming",
            "customroles", "giveaway", "boycott", "automations",
            "fun", "voice", "adminsetup", "ignore", "roleassign",
            "report", "antispam", "messagelog", "botprofile",
            "backup", "altdetector", "slowmode", "raidalert", "chatbot",
            "massmention", "antivanity", "stafflog", "ownerrecovery", "polish",
            "publicbot", "globalblacklist", "announce"
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded {cog}")
            except Exception as e:
                logger.error(f"Failed to load {cog}: {e}")

        await self.tree.sync()
        logger.info("Command tree synced")

    async def on_ready(self):
        logger.info(f"🛡️ Security Bot online as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name="NeoMonster / 24/7 Protection"
        ))

    # ------------------------------------------------------------
    # FIXED Global error handler – always replies, even after defer
    # ------------------------------------------------------------
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Build the appropriate error embed
        if isinstance(error, app_commands.MissingRole):
            embed = BotEmbed.error("Insufficient Role", str(error))
        elif isinstance(error, app_commands.MissingPermissions):
            embed = BotEmbed.error("Missing Permissions", "You don't have the required Discord permissions.")
        else:
            logger.error(f"Command error: {error}")
            embed = BotEmbed.error("Unexpected Error", "An unexpected error occurred. Please contact an administrator.")

        # Send the reply safely – use followup if already responded
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")


# This block runs only when you start the script directly
if __name__ == "__main__":
    bot = SecurityBot()

    # Attach the bot to the Flask app so the dashboard can see it
    app.config["bot"] = bot

    port = int(os.environ.get("PORT", 5000))   # Railway gives us a PORT, else 5000 locally
    flask_thread = Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": port, "debug": False, "use_reloader": False},
        daemon=True
    )
    flask_thread.start()
    logger.info("Dashboard started on http://0.0.0.0:5000")

    # Now start the bot (this blocks and keeps everything alive)
    bot.run(os.getenv("BOT_TOKEN"))