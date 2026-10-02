import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from datetime import datetime, timezone, timedelta
from formatter import BotEmbed
from checks import staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# Config
FAKE_ACCOUNT_DAYS = 7   # accounts newer than this are marked as fake
REJOIN_WINDOW_DAYS = 7  # shown as (7d) in the rejoin label


class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {guild_id: {code: uses}}
        self.invite_cache = {}

    async def cog_load(self):
        self.bot.loop.create_task(self._initial_cache())

    async def _initial_cache(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.cache_guild_invites(guild)

    # ---------- Invite cache helpers ----------
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
            old_uses = old_cache.get(inv.code, 0)
            if inv.uses > old_uses:
                return inv
        return None

    # ---------- Events ----------
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild.id in self.invite_cache:
            self.invite_cache[invite.guild.id].pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        old_cache = dict(self.invite_cache.get(guild.id, {}))
        used = await self.find_used_invite(guild, old_cache)

        # Refresh cache regardless
        await self.cache_guild_invites(guild)

        if not used or not used.inviter or used.inviter.bot:
            return

        inviter_id = used.inviter.id

        # Fake account?
        account_age = datetime.now(timezone.utc) - member.created_at
        is_fake = account_age < timedelta(days=FAKE_ACCOUNT_DAYS)

        # Rejoin?
        is_rejoin = False
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM invite_records WHERE guild_id = ? AND member_id = ? AND left_at IS NOT NULL "
                "ORDER BY id DESC LIMIT 1",
                (guild.id, member.id)
            )
            past = await cursor.fetchone()
            if past:
                is_rejoin = True

        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO invite_records (guild_id, member_id, inviter_id, joined_at, is_fake, is_rejoin) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (guild.id, member.id, inviter_id, now, 1 if is_fake else 0, 1 if is_rejoin else 0)
            )
            await db.execute(
                "INSERT OR IGNORE INTO invite_stats (guild_id, user_id) VALUES (?, ?)",
                (guild.id, inviter_id)
            )

            # joins always increments (they joined)
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
            # Real joins increase total
            if not is_fake:
                await db.execute(
                    "UPDATE invite_stats SET total = total + 1 WHERE guild_id = ? AND user_id = ?",
                    (guild.id, inviter_id)
                )
            await db.commit()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, inviter_id, is_fake FROM invite_records "
                "WHERE guild_id = ? AND member_id = ? AND left_at IS NULL "
                "ORDER BY id DESC LIMIT 1",
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

    # ---------- /invites ----------
    @app_commands.command(name="invites", description="Show invite stats for a user")
    @app_commands.describe(user="User to check (default: yourself)")
    async def invites_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
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
            total, joins, leaves, fakes, rejoins = (
                row["total"], row["joins"], row["leaves"], row["fakes"], row["rejoins"]
            )

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
        embed.set_footer(
            text=f"Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )
        await interaction.response.send_message(embed=embed)

    # ---------- /invited ----------
    @app_commands.command(name="invited", description="Show who invited a user")
    @app_commands.describe(user="User to check")
    async def invited_cmd(self, interaction: discord.Interaction, user: discord.Member):
        await self._show_inviter(interaction, user)

    # ---------- /inviter ----------
    @app_commands.command(name="inviter", description="Show who invited a user (alias)")
    @app_commands.describe(user="User to check")
    async def inviter_cmd(self, interaction: discord.Interaction, user: discord.Member):
        await self._show_inviter(interaction, user)

    async def _show_inviter(self, interaction, user):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM invite_records WHERE guild_id = ? AND member_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (interaction.guild_id, user.id)
            )
            record = await cursor.fetchone()

        if not record:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Record", f"No invite record found for {user.mention}."),
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
        joined = record["joined_at"][:19].replace("T", " ")
        embed.add_field(name="Joined", value=joined, inline=True)
        if record["is_fake"]:
            embed.add_field(name="Status", value="⚠️ Fake account", inline=True)
        if record["is_rejoin"]:
            embed.add_field(name="Rejoin", value="Yes", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    # ---------- /inviteleaderboard ----------
    @app_commands.command(name="inviteleaderboard", description="Top inviters in this server")
    async def inviteleaderboard(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM invite_stats WHERE guild_id = ? AND total > 0 "
                "ORDER BY total DESC LIMIT 10",
                (interaction.guild_id,)
            )
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Data", "No invite data yet."),
                ephemeral=True
            )

        lines = []
        for idx, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            mention = member.mention if member else f"<@{row['user_id']}>"
            lines.append(
                f"**#{idx}** {mention} • **{row['total']}** Invites "
                f"({row['joins']} Joins, {row['leaves']} Leaves, "
                f"{row['fakes']} Fakes, {row['rejoins']} Rejoins)"
            )

        embed = discord.Embed(
            title="Invite Leaderboard",
            description="\n".join(lines),
            color=0x2ECC71,
            timestamp=interaction.created_at
        )
        embed.set_footer(text="NeoMonster • Invite Tracking")
        await interaction.response.send_message(embed=embed)

    # ---------- /manageinvites ----------
    @app_commands.command(name="manageinvites", description="Manage a user's invite stats (staff only)")
    @app_commands.describe(
        user="User to modify",
        stat="Which stat to modify",
        action="Add or remove",
        count="Amount to add/remove"
    )
    @app_commands.choices(
        stat=[
            app_commands.Choice(name="total", value="total"),
            app_commands.Choice(name="joins", value="joins"),
            app_commands.Choice(name="leaves", value="leaves"),
            app_commands.Choice(name="fakes", value="fakes"),
            app_commands.Choice(name="rejoins", value="rejoins"),
        ],
        action=[
            app_commands.Choice(name="add", value="add"),
            app_commands.Choice(name="remove", value="remove"),
        ]
    )
    @staff_only()
    async def manageinvites(self, interaction, user: discord.Member, stat: str, action: str, count: int):
        if count < 0:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Invalid", "Count must be positive."),
                ephemeral=True
            )

        sign = 1 if action == "add" else -1
        delta = count * sign

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO invite_stats (guild_id, user_id) VALUES (?, ?)",
                (interaction.guild_id, user.id)
            )
            await db.execute(
                f"UPDATE invite_stats SET {stat} = {stat} + ? "
                f"WHERE guild_id = ? AND user_id = ?",
                (delta, interaction.guild_id, user.id)
            )
            await db.commit()

        embed = BotEmbed.success(
            "Invite Stats Updated",
            f"{'Added' if sign > 0 else 'Removed'} **{count}** to **{stat}** for {user.mention}."
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
        await db.commit()
    await bot.add_cog(Invites(bot))