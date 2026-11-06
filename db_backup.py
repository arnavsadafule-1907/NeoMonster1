import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import asyncio
import aiosqlite
from datetime import datetime
from logger import setup_logging
from checks import admin_only
from formatter import BotEmbed
from db import get_db_path

logger = setup_logging()

BACKUP_CHANNEL_ID = os.getenv("BACKUP_CHANNEL_ID")
MAX_BACKUPS = 20
BACKUP_INTERVAL_MINUTES = 2


class DBBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = get_db_path()
        self.last_uploaded_size = 0
        self.backup_loop.start()

    def cog_unload(self):
        self.backup_loop.cancel()

    @tasks.loop(minutes=BACKUP_INTERVAL_MINUTES)
    async def backup_loop(self):
        await self.upload_backup(silent=True)

    @backup_loop.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)

    async def _create_atomic_copy(self, dest_path: str):
        """
        Use SQLite's built-in backup API to create an atomic, WAL-safe copy.
        This includes all recent writes that may still be in the -wal file.
        """
        async with aiosqlite.connect(self.db_path, timeout=10.0) as src:
            async with aiosqlite.connect(dest_path, timeout=10.0) as dst:
                await src.backup(dst)

    async def upload_backup(self, silent=False):
        if not BACKUP_CHANNEL_ID:
            if not silent:
                logger.warning("Backup skipped: BACKUP_CHANNEL_ID not set in env")
            return

        if not os.path.exists(self.db_path):
            if not silent:
                logger.warning(f"Backup skipped: DB not found at {self.db_path}")
            return

        current_size = os.path.getsize(self.db_path)
        if current_size < 4000:
            if not silent:
                logger.info(f"Backup skipped: DB too small ({current_size} bytes)")
            return

        if current_size == self.last_uploaded_size:
            if not silent:
                logger.info("Backup skipped: no size change since last upload")
            return

        try:
            channel = self.bot.get_channel(int(BACKUP_CHANNEL_ID))
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(int(BACKUP_CHANNEL_ID))
                except (discord.NotFound, discord.Forbidden) as e:
                    logger.error(f"Backup failed: cannot fetch channel {BACKUP_CHANNEL_ID}: {e}")
                    return

            os.makedirs("./data/tmp", exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            temp_path = f"./data/tmp/security_{timestamp}.db"

            # Atomic WAL-safe copy
            await self._create_atomic_copy(temp_path)

            try:
                with open(temp_path, "rb") as f:
                    file = discord.File(f, filename=f"security_{timestamp}.db")
                    await channel.send(
                        content=f"🗄️ **Auto-Backup** – `{timestamp}` UTC ({current_size} bytes)",
                        file=file
                    )
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            self.last_uploaded_size = current_size
            await self._cleanup_old_backups(channel)
            logger.info(f"✅ DB backup uploaded: {timestamp} ({current_size} bytes)")

        except discord.Forbidden:
            logger.error(
                f"Backup failed: bot lacks Upload Attachments permission "
                f"in channel {BACKUP_CHANNEL_ID}"
            )
        except discord.HTTPException as e:
            logger.error(f"Backup failed: Discord API error: {e}")
        except Exception as e:
            logger.error(f"❌ Backup failed: {type(e).__name__}: {e}")

    async def _cleanup_old_backups(self, channel):
        try:
            backups = []
            async for msg in channel.history(limit=100):
                if msg.attachments and any(a.filename.endswith(".db") for a in msg.attachments):
                    backups.append(msg)

            for msg in backups[MAX_BACKUPS:]:
                try:
                    await msg.delete()
                except (discord.Forbidden, discord.HTTPException):
                    pass
        except Exception as e:
            logger.warning(f"Backup cleanup failed: {e}")

    @app_commands.command(name="forcebackup", description="Manually save the database to Discord instantly")
    @admin_only()
    async def forcebackup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not BACKUP_CHANNEL_ID:
            embed = BotEmbed.error("Not Configured", "BACKUP_CHANNEL_ID is not set. Ask the bot owner to configure it.")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        # Force upload even if DB size unchanged
        self.last_uploaded_size = 0
        await self.upload_backup(silent=False)

        embed = BotEmbed.success("Backup Saved", "Your latest changes are now safely saved to Discord.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DBBackup(bot))