import os
import asyncio
import discord
import requests
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from logger import setup_logging
from db import init_db
from dashboard import app
from threading import Thread

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
        logger.warning("⚠️ BACKUP_CHANNEL_ID missing. Skipping DB restore.")
        return

    logger.info("⏳ Checking Discord for database backups...")
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error(f"❌ Failed to read backup channel (HTTP {resp.status_code})")
            return

        messages = resp.json()
        for msg in messages:
            if msg.get("attachments"):
                for att in msg["attachments"]:
                    if att["filename"].endswith(".db"):
                        logger.info(f"Found backup: {att['filename']}. Downloading...")
                        file_resp = requests.get(att["url"], timeout=15)
                        
                        # Check if file is bigger than 4000 bytes
                        if file_resp.status_code == 200:
                            file_size = len(file_resp.content)
                            logger.info(f"Downloaded file size: {file_size} bytes")
                            
                            if file_size > 4000:
                                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                                with open(db_path, "wb") as f:
                                    f.write(file_resp.content)
                                logger.info(f"✅ Restored database from Discord ({file_size} bytes)")
                                return
                            else:
                                logger.warning(f"⚠️ Skipped backup {att['filename']} because it is too small ({file_size} bytes).")
                            
        logger.info("ℹ️ No valid previous backup found. Starting fresh.")
    except Exception as e:
        logger.error(f"❌ Error restoring backup: {e}")


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
        try:
            await init_db()
            logger.info("Database ready")
        except Exception as e:
            logger.error(f"Database init failed: {e}")

        cogs = [
            "antinuke", "config", "recovery", "help",
            "moderation", "utility", "welcoming",
            "customroles", "giveaway", "boycott", "automations",
            "fun", "voice", "adminsetup", "ignore", "roleassign",
            "report", "antispam", "botprofile",
            "backup", "altdetector", "slowmode", "raidalert", "chatbot",
            "massmention", "antivanity", "stafflog", "ownerrecovery", "polish",
            "publicbot", "globalblacklist", "announce",
            "ticket", "serverlogger", "botwhitelist", "sync",
            "extraowner", "dmall", "staffstats", "leave", "giverole",
            "staffleaderboard", "ticketcleanup",
            "db_backup", "sticky", "serverstatus", "minecraft",
            "tracking",
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