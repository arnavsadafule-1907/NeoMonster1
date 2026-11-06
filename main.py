import os
import asyncio
import importlib
import discord
import requests
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from logger import setup_logging
from db import init_db
from dashboard import app
from threading import Thread
from formatter import BotEmbed
try:
    init_emojis = importlib.import_module("utils.emoji_manager").init_emojis
except ModuleNotFoundError:
    def init_emojis(bot):
        logger.warning("Emoji manager unavailable; continuing without custom emojis.")

load_dotenv()
logger = setup_logging()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN not set.")
    exit(1)

try:
    owner_ids_str = os.getenv("OWNER_IDS", "")
    OWNER_IDS = set(int(x.strip()) for x in owner_ids_str.split(",") if x.strip()) if owner_ids_str else set()
except ValueError:
    OWNER_IDS = set()

TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")


def restore_db_before_startup():
    channel_id = os.getenv("BACKUP_CHANNEL_ID")
    db_path = os.getenv("DATABASE_PATH", "./data/security.db")

    if not channel_id or channel_id == "0":
        return

    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return

        messages = resp.json()
        best_file_url = None
        best_file_size = 0

        for msg in messages:
            if msg.get("attachments"):
                for att in msg["attachments"]:
                    if att["filename"].endswith(".db"):
                        size = att.get("size", 0)
                        if size > best_file_size:
                            best_file_size = size
                            best_file_url = att["url"]

        if not best_file_url:
            return

        file_resp = requests.get(best_file_url, timeout=20)
        if file_resp.status_code == 200:
            content = file_resp.content
            if len(content) < 10000 or not content.startswith(b'SQLite format 3\x00'):
                return

            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            with open(db_path, "wb") as f:
                f.write(content)
    except Exception as e:
        logger.error(f"Database restore failed: {e}")


class SecurityBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.bans = True
        intents.voice_states = True
        super().__init__(command_prefix="/", intents=intents)
        self.owner_ids = OWNER_IDS

    async def setup_hook(self):
        init_emojis(self)
        try:
            await init_db()
            logger.info("Database ready")
        except Exception as e:
            logger.error(f"Database init failed: {e}")

        cogs = [
            "antinuke", "config", "recovery", "help",
            "moderation", "utility", "welcoming",
            "boycott", "automations", "voice", "adminsetup", "ignore", "roleassign",
            "report", "antispam", "botprofile", "backup", "altdetector", "slowmode",
            "raidalert", "chatbot", "massmention", "antivanity", "stafflog", "ownerrecovery",
            "polish", "publicbot", "globalblacklist", "announce", "ticket", "serverlogger",
            "botwhitelist", "sync", "extraowner", "dmall", "staffstats", "leave", "giverole",
            "removerole", "staffleaderboard", "ticketcleanup", "db_backup", "sticky", "serverstatus",
            "minecraft", "tracking", "globalbackup", "serverwhitelist", "giveaway", "mongo_backup"
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded {cog}")
            except Exception as e:
                logger.error(f"Failed to load {cog}: {e}")

        self.tree.interaction_check = self.global_blacklist_check

        try:
            if TEST_GUILD_ID:
                guild = discord.Object(id=int(TEST_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await asyncio.wait_for(self.tree.sync(guild=guild), timeout=30)
                logger.info(f"Command tree synced to test guild ({len(synced)} commands)")
            else:
                synced = await asyncio.wait_for(self.tree.sync(), timeout=60)
                logger.info(f"Command tree synced globally ({len(synced)} commands)")
        except Exception as e:
            logger.error(f"Command tree sync failed: {e}")

    async def global_blacklist_check(self, interaction: discord.Interaction) -> bool:
        try:
            global_blacklist_cog = self.get_cog("GlobalBlacklist")
            if global_blacklist_cog and await global_blacklist_cog.is_blacklisted(interaction.user.id):
                await interaction.response.send_message("⛔ You are globally blacklisted.", ephemeral=False)
                return False
        except Exception:
            pass
        return True

    async def on_ready(self):
        logger.info(f"🛡️ Security Bot online as {self.user}")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name="NeoMonster / 24/7 Protection"
        ))

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            return await interaction.response.send_message(
                f"⏳ **Slow down!** Try again in `{error.retry_after:.1f}s`.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.MissingRole):
            embed = BotEmbed.error("Insufficient Role", str(error))
        elif isinstance(error, app_commands.MissingPermissions):
            embed = BotEmbed.error("Missing Permissions", "You don't have the required Discord permissions.")
        elif isinstance(error, app_commands.CheckFailure):
            embed = BotEmbed.error("Access Denied", "You do not have permission to execute this command.")
        else:
            logger.error(f"Command error: {error}")
            embed = BotEmbed.error("Unexpected Error", "An unexpected error occurred.")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")


if __name__ == "__main__":
    restore_db_before_startup()

    bot = SecurityBot()
    app.config["bot"] = bot

    port = int(os.environ.get("PORT", 5000))
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": port, "debug": False, "use_reloader": False}, daemon=True)
    flask_thread.start()
    logger.info(f"Dashboard started on http://0.0.0.0:{port}")

    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
    finally:
        try:
            mongo_module = importlib.import_module("utils.mongo")
            close_mongo = getattr(mongo_module, "close_mongo", None)
            if callable(close_mongo):
                asyncio.run(close_mongo())
        except Exception:
            pass