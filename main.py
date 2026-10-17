import os
import asyncio
import discord
import aiohttp  # Added this
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from logger import setup_logging
from db import init_db
from dashboard import app
from threading import Thread
from formatter import BotEmbed

load_dotenv()
logger = setup_logging()

try:
    owner_ids_str = os.getenv("OWNER_IDS", "")
    if owner_ids_str:
        OWNER_IDS = set(int(x.strip()) for x in owner_ids_str.split(",") if x.strip())
    else:
        OWNER_IDS = set()
except ValueError:
    OWNER_IDS = set()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN not set.")
    exit(1)

TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

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

    async def _restore_db_from_discord(self):
        """Downloads the latest .db file from the backup channel BEFORE loading the DB."""
        channel_id = os.getenv("BACKUP_CHANNEL_ID")
        db_path = os.getenv("DATABASE_PATH", "./data/security.db")

        if not channel_id:
            logger.warning("⚠️ BACKUP_CHANNEL_ID missing. Skipping DB restore.")
            return

        logger.info("⏳ Checking Discord for database backups...")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bot {BOT_TOKEN}"}
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10"
            
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"❌ Failed to read backup channel (HTTP {resp.status})")
                        return
                    messages = await resp.json()

                for msg in messages:
                    if msg.get("attachments"):
                        for att in msg["attachments"]:
                            if att["filename"].endswith(".db"):
                                async with session.get(att["url"]) as file_resp:
                                    if file_resp.status == 200:
                                        data = await file_resp.read()
                                        os.makedirs(os.path.dirname(db_path), exist_ok=True)
                                        with open(db_path, "wb") as f:
                                            f.write(data)
                                        logger.info(f"✅ Restored database from Discord ({len(data)} bytes)")
                                        return
                logger.info("ℹ️ No previous backup found. Starting fresh.")
            except Exception as e:
                logger.error(f"❌ Error restoring backup: {e}")

    async def setup_hook(self):
        # 1. RESTORE DB FIRST (Before anything else)
        await self._restore_db_from_discord()

        # 2. Initialize the restored DB
        try:
            await init_db()
            logger.info("Database ready")
        except Exception as e:
            logger.error(f"Database init failed: {e}")

        # 3. Load cogs
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