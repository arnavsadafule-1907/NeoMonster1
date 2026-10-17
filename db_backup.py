import discord
from discord.ext import commands, tasks
import os
import shutil
import asyncio
from datetime import datetime
from logger import setup_logging

logger = setup_logging()

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
BACKUP_CHANNEL_ID = os.getenv("BACKUP_CHANNEL_ID")
MAX_BACKUPS = 20 
BACKUP_INTERVAL_HOURS = 6

class DBBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_loop.start()

    def cog_unload(self):
        self.backup_loop.cancel()

    @tasks.loop(hours=BACKUP_INTERVAL_HOURS)
    async def backup_loop(self):
        await self.upload_backup()

    @backup_loop.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()
        # Wait 60 seconds after boot before the first backup to let things settle
        await asyncio.sleep(60)

    async def upload_backup(self):
        if not BACKUP_CHANNEL_ID or not os.path.exists(DATABASE_PATH):
            return

        # Safety lock: less than 4000 bytes means the database is totally empty
        if os.path.getsize(DATABASE_PATH) < 4000:
            logger.warning("⚠️ Database is too small (empty). Skipping backup.")
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
                await channel.send(content=f"🗄️ **Auto-Backup** – `{timestamp}` UTC", file=file)

            os.remove(temp_path)
            await self._cleanup_old_backups(channel)
            logger.info(f"✅ DB backup uploaded: {timestamp}")

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")

    async def _cleanup_old_backups(self, channel):
        backups = []
        async for msg in channel.history(limit=100):
            if msg.attachments and any(a.filename.endswith(".db") for a in msg.attachments):
                backups.append(msg)
        
        # Only delete if we have more than 20 backups
        for msg in backups[MAX_BACKUPS:]:
            try:
                await msg.delete()
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(DBBackup(bot))