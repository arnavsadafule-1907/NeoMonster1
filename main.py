import os
import asyncio
import discord
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

# ---------- Safely parse OWNER_IDS ----------
try:
    owner_ids_str = os.getenv("OWNER_IDS", "")
    if owner_ids_str:
        OWNER_IDS = set(int(x.strip()) for x in owner_ids_str.split(",") if x.strip())
    else:
        OWNER_IDS = set()
except ValueError:
    OWNER_IDS = set()
    logger.warning("OWNER_IDS environment variable contains invalid values – ignoring.")

# ---------- Check for required token ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN not set in environment variables. Bot cannot start.")
    exit(1)

# ---------- Optional: test guild ID for fast sync during dev ----------
# Set TEST_GUILD_ID in Render env if you want guild-only sync (instant, no rate limits).
# Leave it unset in production to sync globally.
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

    async def setup_hook(self):
        # ---------- Database ----------
        try:
            await init_db()
            logger.info("Database ready")
        except Exception as e:
            logger.error(f"Database init failed: {e}")

        # ---------- Load cogs ----------
        cogs = [
            "antinuke", "config", "recovery", "help",
            "moderation", "utility", "automod", "welcoming",
            "customroles", "giveaway", "boycott", "automations",
            "fun", "voice", "adminsetup", "ignore", "roleassign",
            "report", "antispam", "messagelog", "botprofile",
            "backup", "altdetector", "slowmode", "raidalert", "chatbot",
            "massmention", "antivanity", "stafflog", "ownerrecovery", "polish",
            "publicbot", "globalblacklist", "announce",
            "ticket", "serverlogger", "poll", "botwhitelist", "sync",
            "extraowner", "dmall", "staffstats", "leave", "giverole",
            "removerole", "staffleaderboard", "ticketcleanup",
            "db_backup", "sticky",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded {cog}")
            except Exception as e:
                logger.error(f"Failed to load {cog}: {e}")

        # ---------- Register global blacklist check ----------
        self.tree.interaction_check = self.global_blacklist_check

        # ---------- Sync command tree with timeout ----------
        try:
            if TEST_GUILD_ID:
                guild = discord.Object(id=int(TEST_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await asyncio.wait_for(self.tree.sync(guild=guild), timeout=30)
                logger.info(f"Command tree synced to test guild ({len(synced)} commands)")
            else:
                synced = await asyncio.wait_for(self.tree.sync(), timeout=60)
                logger.info(f"Command tree synced globally ({len(synced)} commands)")
        except asyncio.TimeoutError:
            logger.error("Command tree sync timed out – continuing startup anyway")
        except Exception as e:
            logger.error(f"Command tree sync failed: {e}")

    async def global_blacklist_check(self, interaction: discord.Interaction) -> bool:
        try:
            global_blacklist_cog = self.get_cog("GlobalBlacklist")
            if global_blacklist_cog and await global_blacklist_cog.is_blacklisted(interaction.user.id):
                await interaction.response.send_message(
                    "⛔ You are globally blacklisted from using NeoMonster.",
                    ephemeral=False
                )
                return False
        except Exception:
            pass
        return True

    async def on_ready(self):
        logger.info(f"🛡️ Security Bot online as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="NeoMonster / 24/7 Protection"
        ))

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            embed = BotEmbed.error("Insufficient Role", str(error))
        elif isinstance(error, app_commands.MissingPermissions):
            embed = BotEmbed.error("Missing Permissions", "You don't have the required Discord permissions.")
        else:
            logger.error(f"Command error: {error}")
            embed = BotEmbed.error("Unexpected Error", "An unexpected error occurred. Please contact an administrator.")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=False)
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")


if __name__ == "__main__":
    bot = SecurityBot()
    app.config["bot"] = bot

    # ---------- Start Flask dashboard in background ----------
    port = int(os.environ.get("PORT", 5000))
    flask_thread = Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": port, "debug": False, "use_reloader": False},
        daemon=True
    )
    flask_thread.start()
    logger.info(f"Dashboard started on http://0.0.0.0:{port}")

    # ---------- Start Discord bot ----------
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.critical("Login failed – BOT_TOKEN is invalid.")
    except discord.PrivilegedIntentsRequired:
        logger.critical("Privileged intents not enabled in the Discord Developer Portal.")
    except Exception as e:
        logger.critical(f"Bot crashed on startup: {e}")