import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import os
from datetime import datetime, timezone
from formatter import BotEmbed
from checks import staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")


class MessageStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {guild_id: {user_id: pending_count}}
        self.cache = {}
        self.flush_loop.start()

    def cog_unload(self):
        self.flush_loop.cancel()

    @tasks.loop(seconds=30)
    async def flush_loop(self):
        await self.flush_cache()

    @flush_loop.before_loop
    async def before_flush(self):
        await self.bot.wait_until_ready()

    async def flush_cache(self):
        if not self.cache:
            return
        snapshot = self.cache
        self.cache = {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        async with aiosqlite.connect(DB_PATH) as db:
            for guild_id, users in snapshot.items():
                for user_id, count in users.items():
                    await db.execute(
                        "INSERT OR IGNORE INTO message_stats "
                        "(guild_id, user_id, all_time, daily, daily_date) "
                        "VALUES (?, ?, 0, 0, ?)",
                        (guild_id, user_id, today)
                    )
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT daily_date FROM message_stats "
                        "WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id)
                    )
                    row = await cursor.fetchone()
                    if row and row["daily_date"] != today:
                        await db.execute(
                            "UPDATE message_stats SET daily = 0, daily_date = ? "
                            "WHERE guild_id = ? AND user_id = ?",
                            (today, guild_id, user_id)
                        )
                    await db.execute(
                        "UPDATE message_stats SET all_time = all_time + ?, "
                        "daily = daily + ? WHERE guild_id = ? AND user_id = ?",
                        (count, count, guild_id, user_id)
                    )
            await db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        gid = message.guild.id
        uid = message.author.id
        self.cache.setdefault(gid, {})
        self.cache[gid][uid] = self.cache[gid].get(uid, 0) + 1

    # ---------- /messages ----------
    @app_commands.command(name="messages", description="Show message stats for a user")
    @app_commands.describe(user="User to check (default: yourself)")
    async def messages_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        await self.flush_cache()

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT all_time, daily FROM message_stats "
                "WHERE guild_id = ? AND user_id = ?",
                (interaction.guild_id, user.id)
            )
            row = await cursor.fetchone()

        all_time = row["all_time"] if row else 0
        daily = row["daily"] if row else 0

        embed = discord.Embed(
            title=f"{user.display_name}'s Messages",
            description=(
                f"**All time** • {all_time} messages in this server !\n"
                f"**Today** • {daily} messages in this server"
            ),
            color=0x3B82F6,
            timestamp=interaction.created_at
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Messages are being updated in real-time")
        await interaction.response.send_message(embed=embed)

    # ---------- /msgleaderboard ----------
    @app_commands.command(name="msgleaderboard", description="Top message senders in this server")
    async def msgleaderboard(self, interaction: discord.Interaction):
        await self.flush_cache()

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM message_stats WHERE guild_id = ? "
                "ORDER BY all_time DESC LIMIT 10",
                (interaction.guild_id,)
            )
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Data", "No message data yet."),
                ephemeral=True
            )

        lines = []
        for idx, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            mention = member.mention if member else f"<@{row['user_id']}>"
            lines.append(f"**#{idx}** {mention} • **{row['all_time']}** messages")

        embed = discord.Embed(
            title="Messages Leaderboard",
            description="The messages are being updated in real-time!\n\n" + "\n".join(lines),
            color=0x3B82F6,
            timestamp=interaction.created_at
        )
        embed.set_footer(text="NeoMonster • Message Tracking")
        await interaction.response.send_message(embed=embed)

    # ---------- /managemsg ----------
    @app_commands.command(name="managemsg", description="Manage a user's message stats (staff only)")
    @app_commands.describe(
        user="User to modify",
        stat="Which stat to modify",
        action="Add or remove",
        count="Amount to add/remove"
    )
    @app_commands.choices(
        stat=[
            app_commands.Choice(name="daily", value="daily"),
            app_commands.Choice(name="alltime", value="all_time"),
        ],
        action=[
            app_commands.Choice(name="add", value="add"),
            app_commands.Choice(name="remove", value="remove"),
        ]
    )
    @staff_only()
    async def managemsg(self, interaction, user: discord.Member, stat: str, action: str, count: int):
        if count < 0:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Invalid", "Count must be positive."),
                ephemeral=True
            )

        sign = 1 if action == "add" else -1
        delta = count * sign
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO message_stats "
                "(guild_id, user_id, all_time, daily, daily_date) "
                "VALUES (?, ?, 0, 0, ?)",
                (interaction.guild_id, user.id, today)
            )
            await db.execute(
                f"UPDATE message_stats SET {stat} = MAX(0, {stat} + ?) "
                f"WHERE guild_id = ? AND user_id = ?",
                (delta, interaction.guild_id, user.id)
            )
            await db.commit()

        label = "Daily" if stat == "daily" else "All-time"
        embed = BotEmbed.success(
            "Message Stats Updated",
            f"{'Added' if sign > 0 else 'Removed'} **{count}** to **{label}** for {user.mention}."
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                all_time INTEGER DEFAULT 0,
                daily INTEGER DEFAULT 0,
                daily_date TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.commit()
    await bot.add_cog(MessageStats(bot))