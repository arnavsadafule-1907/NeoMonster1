import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import os
from datetime import datetime, timezone, timedelta
from formatter import BotEmbed
from checks import staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

FAKE_ACCOUNT_DAYS = 7
REJOIN_WINDOW_DAYS = 7


class Tracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_cache = {}          # {guild_id: {code: uses}}
        self.msg_cache = {}             # {guild_id: {user_id: pending}}
        self.flush_loop.start()

    async def cog_load(self):
        self.bot.loop.create_task(self._initial_invite_cache())

    def cog_unload(self):
        self.flush_loop.cancel()

    # ============== LAZY TABLE CREATION ==============
    async def _ensure_tables(self):
        """Recreate tables if they were wiped by a DB restore."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_stats (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    total INTEGER DEFAULT 0,
                    joins INTEGER DEFAULT 0,
                    leaves INTEGER DEFAULT 0,
                    fakes INTEGER DEFAULT 0,
                    rejoins INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    member_id INTEGER NOT NULL,
                    inviter_id INTEGER NOT NULL,
                    joined_at TEXT NOT NULL,
                    left_at TEXT,
                    is_fake INTEGER DEFAULT 0,
                    is_rejoin INTEGER DEFAULT 0
                )
            """)
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

    # ============== INVITE CACHE ==============
    async def _initial_invite_cache(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.cache_guild_invites(guild)

    async def cache_guild_invites(self, guild):
        try:
            invites = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            return
        self.invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}

    async def find_used_invite(self, guild, old_cache):
        try:
            new_invites = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            return None
        for inv in new_invites:
            if inv.uses > old_cache.get(inv.code, 0):
                return inv
        return None

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild.id in self.invite_cache:
            self.invite_cache[invite.guild.id].pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self._ensure_tables()
        guild = member.guild
        old_cache = dict(self.invite_cache.get(guild.id, {}))
        used = await self.find_used_invite(guild, old_cache)
        await self.cache_guild_invites(guild)

        if not used or not used.inviter or used.inviter.bot:
            return

        inviter_id = used.inviter.id
        account_age = datetime.now(timezone.utc) - member.created_at
        is_fake = account_age < timedelta(days=FAKE_ACCOUNT_DAYS)

        is_rejoin = False
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM invite_records WHERE guild_id = ? AND member_id = ? AND left_at IS NOT NULL LIMIT 1",
                (guild.id, member.id)
            )
            if await cursor.fetchone():
                is_rejoin = True

        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO invite_records (guild_id, member_id, inviter_id, joined_at, is_fake, is_rejoin) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (guild.id, member.id, inviter_id, now, int(is_fake), int(is_rejoin))
            )
            await db.execute(
                "INSERT OR IGNORE INTO invite_stats (guild_id, user_id) VALUES (?, ?)",
                (guild.id, inviter_id)
            )
            await db.execute(
                "UPDATE invite_stats SET joins = joins + 1 WHERE guild_id = ? AND user_id = ?",
                (guild.id, inviter_id)
            )
            if is_fake:
                await db.execute(
                    "UPDATE invite_stats SET fakes = fakes + 1 WHERE guild_id = ? AND user_id = ?",
                    (guild.id, inviter_id)
                )
            if is_rejoin:
                await db.execute(
                    "UPDATE invite_stats SET rejoins = rejoins + 1 WHERE guild_id = ? AND user_id = ?",
                    (guild.id, inviter_id)
                )
            if not is_fake:
                await db.execute(
                    "UPDATE invite_stats SET total = total + 1 WHERE guild_id = ? AND user_id = ?",
                    (guild.id, inviter_id)
                )
            await db.commit()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self._ensure_tables()
        guild = member.guild
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, inviter_id, is_fake FROM invite_records "
                "WHERE guild_id = ? AND member_id = ? AND left_at IS NULL ORDER BY id DESC LIMIT 1",
                (guild.id, member.id)
            )
            record = await cursor.fetchone()
            if not record:
                return
            now = datetime.now(timezone.utc).isoformat()
            await db.execute("UPDATE invite_records SET left_at = ? WHERE id = ?", (now, record["id"]))
            await db.execute(
                "UPDATE invite_stats SET leaves = leaves + 1 WHERE guild_id = ? AND user_id = ?",
                (guild.id, record["inviter_id"])
            )
            if not record["is_fake"]:
                await db.execute(
                    "UPDATE invite_stats SET total = total - 1 WHERE guild_id = ? AND user_id = ?",
                    (guild.id, record["inviter_id"])
                )
            await db.commit()

    # ============== MESSAGE TRACKING ==============
    @tasks.loop(seconds=30)
    async def flush_loop(self):
        await self._ensure_tables()
        await self._flush_messages()

    @flush_loop.before_loop
    async def before_flush(self):
        await self.bot.wait_until_ready()

    async def _flush_messages(self):
        if not self.msg_cache:
            return
        snapshot = self.msg_cache
        self.msg_cache = {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            for gid, users in snapshot.items():
                for uid, count in users.items():
                    await db.execute(
                        "INSERT OR IGNORE INTO message_stats (guild_id, user_id, all_time, daily, daily_date) "
                        "VALUES (?, ?, 0, 0, ?)",
                        (gid, uid, today)
                    )
                    cursor = await db.execute(
                        "SELECT daily_date FROM message_stats WHERE guild_id = ? AND user_id = ?",
                        (gid, uid)
                    )
                    row = await cursor.fetchone()
                    if row and row["daily_date"] != today:
                        await db.execute(
                            "UPDATE message_stats SET daily = 0, daily_date = ? WHERE guild_id = ? AND user_id = ?",
                            (today, gid, uid)
                        )
                    await db.execute(
                        "UPDATE message_stats SET all_time = all_time + ?, daily = daily + ? "
                        "WHERE guild_id = ? AND user_id = ?",
                        (count, count, gid, uid)
                    )
            await db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        gid, uid = message.guild.id, message.author.id
        self.msg_cache.setdefault(gid, {})
        self.msg_cache[gid][uid] = self.msg_cache[gid].get(uid, 0) + 1

    # ============== INVITE COMMANDS ==============
    @app_commands.command(name="invites", description="Show invite stats for a user")
    @app_commands.describe(user="User to check (default: yourself)")
    async def invites_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        await self._ensure_tables()
        user = user or interaction.user
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM invite_stats WHERE guild_id = ? AND user_id = ?",
                (interaction.guild_id, user.id)
            )
            row = await cursor.fetchone()

        total = joins = leaves = fakes = rejoins = 0
        if row:
            total, joins, leaves, fakes, rejoins = row["total"], row["joins"], row["leaves"], row["fakes"], row["rejoins"]

        embed = discord.Embed(
            title="Invite Log",
            description=f"» {user.mention} has **{total}** invites",
            color=0x2ECC71,
            timestamp=interaction.created_at
        )
        embed.add_field(
            name="\u200b",
            value=(
                f"**Joins :** {joins}\n"
                f"**Left :** {leaves}\n"
                f"**Fake :** {fakes}\n"
                f"**Rejoins :** {rejoins} ({REJOIN_WINDOW_DAYS}d)"
            ),
            inline=False
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invited", description="Show who invited a user")
    @app_commands.describe(user="User to check")
    async def invited_cmd(self, interaction: discord.Interaction, user: discord.Member):
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM invite_records WHERE guild_id = ? AND member_id = ? ORDER BY id DESC LIMIT 1",
                (interaction.guild_id, user.id)
            )
            record = await cursor.fetchone()

        if not record:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Record", f"No invite record for {user.mention}."),
                ephemeral=True
            )

        inviter = interaction.guild.get_member(record["inviter_id"])
        inviter_text = inviter.mention if inviter else f"<@{record['inviter_id']}>"

        embed = discord.Embed(
            title="Invited By",
            description=f"{user.mention} was invited by {inviter_text}",
            color=0x2ECC71,
            timestamp=interaction.created_at
        )
        embed.add_field(name="Joined", value=record["joined_at"][:19].replace("T", " "), inline=True)
        if record["is_fake"]:
            embed.add_field(name="Status", value="⚠️ Fake account", inline=True)
        if record["is_rejoin"]:
            embed.add_field(name="Rejoin", value="Yes", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inviteleaderboard", description="Top inviters in this server")
    async def inviteleaderboard(self, interaction: discord.Interaction):
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM invite_stats WHERE guild_id = ? AND total > 0 ORDER BY total DESC LIMIT 10",
                (interaction.guild_id,)
            )
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Data", "No invite data yet."), ephemeral=True
            )

        lines = []
        for idx, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            mention = member.mention if member else f"<@{row['user_id']}>"
            lines.append(
                f"**#{idx}** {mention} • **{row['total']}** Invites "
                f"({row['joins']} Joins, {row['leaves']} Leaves, {row['fakes']} Fakes, {row['rejoins']} Rejoins)"
            )

        embed = discord.Embed(
            title="Invite Leaderboard",
            description="\n".join(lines),
            color=0x2ECC71,
            timestamp=interaction.created_at
        )
        embed.set_footer(text="NeoMonster • Invite Tracking")
        await interaction.response.send_message(embed=embed)

    # ============== MESSAGE COMMANDS ==============
    @app_commands.command(name="messages", description="Show message stats for a user")
    @app_commands.describe(user="User to check (default: yourself)")
    async def messages_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        await self._ensure_tables()
        user = user or interaction.user
        await self._flush_messages()

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT all_time, daily FROM message_stats WHERE guild_id = ? AND user_id = ?",
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

    @app_commands.command(name="msgleaderboard", description="Top message senders in this server")
    async def msgleaderboard(self, interaction: discord.Interaction):
        await self._ensure_tables()
        await self._flush_messages()

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM message_stats WHERE guild_id = ? ORDER BY all_time DESC LIMIT 10",
                (interaction.guild_id,)
            )
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Data", "No message data yet."), ephemeral=True
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

    # ============== UNIFIED ADMIN COMMAND ==============
    @app_commands.command(name="managetracking", description="Manage invite or message stats for a user (staff only)")
    @app_commands.describe(
        system="Invite or message stats",
        user="User to modify",
        stat="Which stat",
        action="Add or remove",
        count="Amount"
    )
    @app_commands.choices(
        system=[
            app_commands.Choice(name="invites", value="invites"),
            app_commands.Choice(name="messages", value="messages"),
        ],
        stat=[
            app_commands.Choice(name="total", value="total"),
            app_commands.Choice(name="joins", value="joins"),
            app_commands.Choice(name="leaves", value="leaves"),
            app_commands.Choice(name="fakes", value="fakes"),
            app_commands.Choice(name="rejoins", value="rejoins"),
            app_commands.Choice(name="daily", value="daily"),
            app_commands.Choice(name="alltime", value="all_time"),
        ],
        action=[
            app_commands.Choice(name="add", value="add"),
            app_commands.Choice(name="remove", value="remove"),
        ]
    )
    @staff_only()
    async def managetracking(self, interaction, system: str, user: discord.Member, stat: str, action: str, count: int):
        await self._ensure_tables()

        if count < 0:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Invalid", "Count must be positive."), ephemeral=True
            )

        invite_stats = {"total", "joins", "leaves", "fakes", "rejoins"}
        msg_stats = {"daily", "all_time"}
        if system == "invites" and stat not in invite_stats:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Invalid", "That stat is only for messages."), ephemeral=True
            )
        if system == "messages" and stat not in msg_stats:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Invalid", "That stat is only for invites."), ephemeral=True
            )

        sign = 1 if action == "add" else -1
        delta = count * sign
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if system == "invites":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO invite_stats (guild_id, user_id) VALUES (?, ?)",
                    (interaction.guild_id, user.id)
                )
                await db.execute(
                    f"UPDATE invite_stats SET {stat} = {stat} + ? WHERE guild_id = ? AND user_id = ?",
                    (delta, interaction.guild_id, user.id)
                )
                await db.commit()
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO message_stats (guild_id, user_id, all_time, daily, daily_date) "
                    "VALUES (?, ?, 0, 0, ?)",
                    (interaction.guild_id, user.id, today)
                )
                await db.execute(
                    f"UPDATE message_stats SET {stat} = MAX(0, {stat} + ?) WHERE guild_id = ? AND user_id = ?",
                    (delta, interaction.guild_id, user.id)
                )
                await db.commit()

        label = "invite" if system == "invites" else "message"
        embed = BotEmbed.success(
            "Tracking Updated",
            f"{'Added' if sign > 0 else 'Removed'} **{count}** to **{stat}** ({label}) for {user.mention}."
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                total INTEGER DEFAULT 0,
                joins INTEGER DEFAULT 0,
                leaves INTEGER DEFAULT 0,
                fakes INTEGER DEFAULT 0,
                rejoins INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                left_at TEXT,
                is_fake INTEGER DEFAULT 0,
                is_rejoin INTEGER DEFAULT 0
            )
        """)
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
    await bot.add_cog(Tracking(bot))