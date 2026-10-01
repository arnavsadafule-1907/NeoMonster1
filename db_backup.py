import discord
from discord.ext import commands, tasks
import os
import shutil
import aiohttp
import asyncio
from datetime import datetime
from logger import setup_logging

logger = setup_logging()

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
BACKUP_CHANNEL_ID = os.getenv("BACKUP_CHANNEL_ID")
MAX_BACKUPS = 5
BACKUP_INTERVAL_HOURS = 6


class DBBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_loop.start()

    def cog_unload(self):
        self.backup_loop.cancel()

    # ---------- Startup: schedule restore as a background task ----------
    async def cog_load(self):
        # Do NOT await wait_until_ready() here — it would deadlock setup_hook.
        # Instead, schedule the restore to run once the bot is ready.
        self.bot.loop.create_task(self._post_ready_restore())

    async def _post_ready_restore(self):
        await self.bot.wait_until_ready()
        await self.restore_latest_backup()

    async def restore_latest_backup(self):
        """Download the most recent backup from Discord and replace the local DB."""
        if not BACKUP_CHANNEL_ID:
            logger.warning("⚠️ BACKUP_CHANNEL_ID not set – skipping DB restore.")
            return

        try:
            channel = self.bot.get_channel(int(BACKUP_CHANNEL_ID))
            if not channel:
                logger.warning(f"⚠️ Backup channel {BACKUP_CHANNEL_ID} not found.")
                return

            async for msg in channel.history(limit=20):
                if msg.attachments:
                    attachment = msg.attachments[0]
                    if attachment.filename.endswith(".db"):
                        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    with open(DATABASE_PATH, "wb") as f:
                                        f.write(data)
                                    logger.info(f"✅ Restored database from backup ({len(data)} bytes)")
                                    return
            logger.info("ℹ️ No backup found – starting with fresh database.")
        except Exception as e:
            logger.error(f"❌ Failed to restore backup: {e}")

    # ---------- Periodic: Upload backup ----------
    @tasks.loop(hours=BACKUP_INTERVAL_HOURS)
    async def backup_loop(self):
        await self.upload_backup()

    @backup_loop.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()

    async def upload_backup(self):
        if not BACKUP_CHANNEL_ID:
            return
        if not os.path.exists(DATABASE_PATH):
            logger.warning("⚠️ Database file not found – skipping backup.")
            return

        try:
            channel = self.bot.get_channel(int(BACKUP_CHANNEL_ID))
            if not channel:
                return

            os.makedirs("./data/tmp", exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            temp_path = f"./data/tmp/security_{timestamp}.db"
            shutil.copyfile(DATABASE_PATH, temp_path)

            with open(temp_path, "rb") as f:
                file = discord.File(f, filename=f"security_{timestamp}.db")
                await channel.send(
                    content=f"🗄️ **Auto-Backup** – `{timestamp}` UTC",
                    file=file
                )

            os.remove(temp_path)
            await self._cleanup_old_backups(channel)
            logger.info(f"✅ DB backup uploaded: {timestamp}")

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")

    async def _cleanup_old_backups(self, channel):
        backups = []
        async for msg in channel.history(limit=50):
            if msg.attachments and any(a.filename.endswith(".db") for a in msg.attachments):
                backups.append(msg)
        for msg in backups[MAX_BACKUPS:]:
            try:
                await msg.delete()
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(DBBackup(bot))