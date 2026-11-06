import os
import asyncio
from datetime import datetime, timezone

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

from checks import owner_only
from db import get_db_path
from formatter import BotEmbed
from logger import setup_logging
from ultis.mongo import connect_mongo, get_db as get_mongo, is_connected

logger = setup_logging()

MIRROR_INTERVAL_MINUTES = 5

# Tables mirrored to MongoDB (mirrors all user-facing data)
MIRROR_TABLES = [
    "guild_settings", "whitelist", "antinuke_logs",
    "ticket_metadata", "ticket_types", "ticket_counter", "ticket_panel_config",
    "staff_stats", "leaves", "leave_settings", "leave_panel_config", "staff_logs",
    "extra_owners", "global_blacklist", "guild_blacklist", "bot_whitelist",
    "raid_webhooks", "altdetector_settings", "massmention_settings",
    "antivanity_settings", "report_settings", "antispam_settings",
    "server_whitelists", "sw_users", "sw_roles", "sw_channels",
    "ignored_entities", "log_channels", "sticky_messages",
    "dm_campaigns", "welcoming_settings", "giveaways",
    "invite_stats", "invite_records", "message_stats", "mc_live_panels",
]


async def mirror_sqlite_to_mongo() -> int:
    """Copy all SQLite tables into MongoDB. Returns row count."""
    db = get_mongo()
    if db is None:
        return 0

    sqlite_path = get_db_path()
    if not os.path.exists(sqlite_path):
        return 0

    total = 0
    async with aiosqlite.connect(sqlite_path, timeout=10.0) as sql:
        sql.row_factory = aiosqlite.Row

        for table in MIRROR_TABLES:
            try:
                cursor = await sql.execute(f"SELECT * FROM {table}")
                rows = await cursor.fetchall()
                if not rows:
                    continue

                docs = []
                for row in rows:
                    doc = dict(row)
                    doc["_synced_at"] = datetime.now(timezone.utc)
                    docs.append(doc)

                coll = db[f"mirror_{table}"]
                await coll.delete_many({})
                await coll.insert_many(docs)
                total += len(docs)

            except Exception as e:
                logger.warning(f"MongoDB mirror failed for {table}: {e}")

    await db["mirror_meta"].update_one(
        {"_id": "last_sync"},
        {"$set": {
            "timestamp": datetime.now(timezone.utc),
            "total_rows": total,
            "tables_synced": len(MIRROR_TABLES),
        }},
        upsert=True,
    )
    return total


async def restore_from_mongo(force: bool = False) -> int:
    """Restore tables from MongoDB into SQLite. Only fills empty tables unless force=True."""
    db = get_mongo()
    if db is None:
        return 0

    sqlite_path = get_db_path()
    os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)

    restored = 0
    async with aiosqlite.connect(sqlite_path, timeout=10.0) as sql:
        sql.row_factory = aiosqlite.Row

        for table in MIRROR_TABLES:
            coll = db[f"mirror_{table}"]
            try:
                docs = await coll.find({}).to_list(length=20000)
            except Exception as e:
                logger.warning(f"MongoDB read failed for {table}: {e}")
                continue

            if not docs:
                continue

            try:
                cursor = await sql.execute(f"SELECT COUNT(*) FROM {table}")
                count = (await cursor.fetchone())[0]
            except Exception:
                # Table doesn't exist in SQLite — skip
                continue

            if count > 0 and not force:
                continue

            if force:
                await sql.execute(f"DELETE FROM {table}")

            sample = {k: v for k, v in docs[0].items() if k not in ("_id", "_synced_at")}
            columns = list(sample.keys())
            placeholders = ",".join(["?" for _ in columns])
            insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

            for doc in docs:
                values = []
                for col in columns:
                    v = doc.get(col)
                    if isinstance(v, datetime):
                        v = v.isoformat()
                    values.append(v)
                try:
                    await sql.execute(insert_sql, values)
                    restored += 1
                except Exception as e:
                    logger.warning(f"Restore row failed in {table}: {e}")

        await sql.commit()

    return restored


class MongoBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connected = False
        self.last_sync_rows = 0

    async def cog_load(self):
        self.connected = await connect_mongo() is not None
        if self.connected:
            logger.info("MongoBackup: connected, starting mirror loop")
            # Initial restore before first mirror
            if os.getenv("MONGO_RESTORE_ON_EMPTY", "1") == "1":
                try:
                    restored = await restore_from_mongo(force=False)
                    if restored:
                        logger.info(f"MongoBackup: restored {restored} rows into empty SQLite tables")
                except Exception as e:
                    logger.error(f"MongoBackup initial restore failed: {e}")
            self.mirror_loop.start()
        else:
            logger.info("MongoBackup: MongoDB not configured — cog idle")

    def cog_unload(self):
        if self.mirror_loop.is_running():
            self.mirror_loop.cancel()

    @tasks.loop(minutes=MIRROR_INTERVAL_MINUTES)
    async def mirror_loop(self):
        if not is_connected():
            return
        try:
            self.last_sync_rows = await mirror_sqlite_to_mongo()
        except Exception as e:
            logger.error(f"MongoBackup mirror error: {e}")

    @mirror_loop.before_loop
    async def before_mirror(self):
        await self.bot.wait_until_ready()

    # -------------------- COMMANDS --------------------

    @app_commands.command(name="mongostatus", description="Show MongoDB mirror status")
    async def mongostatus(self, interaction: discord.Interaction):
        if not is_connected():
            embed = BotEmbed.error(
                "MongoDB Not Configured",
                "MONGO_URI is not set on the server. Add it in Render → Environment, then redeploy."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        db = get_mongo()
        try:
            meta = await db["mirror_meta"].find_one({"_id": "last_sync"})
        except Exception:
            meta = None

        embed = BotEmbed.info("MongoDB Mirror Status")
        embed.add_field(name="Connection", value="🟢 Connected", inline=True)
        embed.add_field(name="Database", value=os.getenv("MONGO_DB_NAME", "neomonster"), inline=True)
        embed.add_field(name="Mirror interval", value=f"every {MIRROR_INTERVAL_MINUTES} min", inline=True)

        if meta:
            ts = meta.get("timestamp")
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                ts_str = str(ts)
            embed.add_field(name="Last sync", value=ts_str, inline=False)
            embed.add_field(name="Rows mirrored", value=str(meta.get("total_rows", 0)), inline=True)
            embed.add_field(name="Tables", value=str(meta.get("tables_synced", 0)), inline=True)
        else:
            embed.add_field(name="Last sync", value="No sync yet — waiting for first loop", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="mongobackup", description="Force a MongoDB mirror sync now")
    @owner_only()
    async def mongobackup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not is_connected():
            return await interaction.followup.send(
                embed=BotEmbed.error("Not Configured", "MONGO_URI is not set."), ephemeral=True
            )

        try:
            rows = await mirror_sqlite_to_mongo()
            embed = BotEmbed.success("MongoDB Sync Complete", f"Mirrored **{rows}** rows.")
        except Exception as e:
            embed = BotEmbed.error("Sync Failed", f"```{e}```")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="mongorestore",
        description="Restore SQLite from MongoDB (only fills empty tables unless force)"
    )
    @app_commands.describe(force="⚠️ Delete existing SQLite rows and overwrite with MongoDB data")
    @owner_only()
    async def mongorestore(self, interaction: discord.Interaction, force: bool = False):
        await interaction.response.defer(ephemeral=True)

        if not is_connected():
            return await interaction.followup.send(
                embed=BotEmbed.error("Not Configured", "MONGO_URI is not set."), ephemeral=True
            )

        try:
            rows = await restore_from_mongo(force=force)
            mode = "FORCE OVERWRITE" if force else "fill empty tables only"
            embed = BotEmbed.success(
                "MongoDB Restore Complete",
                f"Restored **{rows}** rows ({mode}).\n"
                f"{'⚠️ Restart the bot to pick up overwritten data.' if force else ''}"
            )
        except Exception as e:
            embed = BotEmbed.error("Restore Failed", f"```{e}```")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(MongoBackup(bot))