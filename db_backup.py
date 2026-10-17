import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import shutil
import asyncio
from datetime import datetime
from logger import setup_logging
from checks import admin_only
from formatter import BotEmbed

logger = setup_logging()

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
BACKUP_CHANNEL_ID = os.getenv("BACKUP_CHANNEL_ID")
MAX_BACKUPS = 20 
BACKUP_INTERVAL_MINUTES = 2  # Saves every 2 minutes!

class DBBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_loop.start()
        self.last_uploaded_size = 0

    def cog_unload(self):
        self.backup_loop.cancel()

    @tasks.loop(minutes=BACKUP_INTERVAL_MINUTES)
    async def backup_loop(self):
        await self.upload_backup(silent=True)

    @backup_loop.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)

    async def upload_backup(self, silent=False):
        if not BACKUP_CHANNEL_ID or not os.path.exists(DATABASE_PATH):
            return

        # 🛑 Safety lock: Don't upload if empty (under 4000 bytes)
        current_size = os.path.getsize(DATABASE_PATH)
        if current_size < 4000:
            return

        # Don't upload if nothing has changed (saves Discord API rate limits)
        if current_size == self.last_uploaded_size:
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
            self.last_uploaded_size = current_size
            await self._cleanup_old_backups(channel)
            
            if not silent:
                logger.info(f"✅ DB backup uploaded: {timestamp}")

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")

    async def _cleanup_old_backups(self, channel):
        backups = []
        async for msg in channel.history(limit=100):
            if msg.attachments and any(a.filename.endswith(".db") for a in msg.attachments):
                backups.append(msg)
        
        for msg in backups[MAX_BACKUPS:]:
            try:
                await msg.delete()
            except Exception:
                pass

    @app_commands.command(name="forcebackup", description="Manually save the database to Discord instantly")
    @admin_only()
    async def forcebackup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.upload_backup(silent=False)
        await interaction.followup.send(
            embed=BotEmbed.success("Backup Saved", "Your latest changes are now safely saved to Discord."),
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(DBBackup(bot))
    