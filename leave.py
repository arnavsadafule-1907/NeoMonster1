import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import os
from datetime import date, datetime, timedelta
from formatter import BotEmbed
from checks import ticket_staff_only, admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class Leave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_leaves.start()

    def cog_unload(self):
        self.check_leaves.cancel()

    async def get_leave_role(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT role_id FROM leave_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_leave_role(self, guild_id: int, role_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO leave_settings (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
            await db.commit()

    # ---------- /leavesetup (admin only) ----------
    @app_commands.command(name="leavesetup", description="Set the 'On Leave' role for the server")
    @app_commands.describe(role="The role to give staff on leave")
    @admin_only()
    async def leave_setup(self, interaction: discord.Interaction, role: discord.Role):
        await self.set_leave_role(interaction.guild_id, role.id)
        embed = BotEmbed.success("Leave Role Set", f"The {role.mention} role will be assigned to staff on leave.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /leave take ----------
    @app_commands.command(name="leave", description="Manage your leave status")
    @app_commands.describe(action="Take leave or return to work", start_date="Start date (YYYY-MM-DD)", end_date="End date (YYYY-MM-DD)", reason="Reason for leave")
    @app_commands.choices(action=[
        app_commands.Choice(name="Take Leave", value="take"),
        app_commands.Choice(name="Return to Work", value="return"),
    ])
    @ticket_staff_only()
    async def leave_cmd(self, interaction: discord.Interaction, action: str, start_date: str = None, end_date: str = None, reason: str = None):
        if action == "take":
            await self.start_leave(interaction, start_date, end_date, reason)
        elif action == "return":
            await self.end_leave_early(interaction)

    async def start_leave(self, interaction: discord.Interaction, start_str: str, end_str: str, reason: str):
        # Parse dates
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            embed = BotEmbed.error("Invalid Date", "Use the format `YYYY-MM-DD`.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if start > end:
            embed = BotEmbed.error("Invalid Range", "Start date must be before or equal to end date.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if start < date.today():
            embed = BotEmbed.error("Past Date", "Start date cannot be in the past.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Check for active leave
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT id FROM leaves WHERE guild_id=? AND user_id=? AND active=1", (interaction.guild_id, interaction.user.id))
            if await cursor.fetchone():
                embed = BotEmbed.error("Already on Leave", "You already have an active leave. Use `/leave return` to end it.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Get leave role
        role_id = await self.get_leave_role(interaction.guild_id)
        if not role_id:
            embed = BotEmbed.error("Not Configured", "An admin must set the leave role first with `/leavesetup`.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        role = interaction.guild.get_role(role_id)
        if not role:
            embed = BotEmbed.error("Role Missing", "The configured leave role no longer exists.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Assign role
        try:
            await interaction.user.add_roles(role, reason="Staff leave")
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I cannot assign the leave role. Check my role hierarchy and permissions.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Insert leave record
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO leaves (guild_id, user_id, start_date, end_date, reason, active) VALUES (?,?,?,?,?,1)",
                (interaction.guild_id, interaction.user.id, start.isoformat(), end.isoformat(), reason or "")
            )
            await db.commit()

        # DM confirmation
        try:
            embed = discord.Embed(
                title="✅ Leave Registered",
                description=f"**Start:** {start}\n**End:** {end}\n**Reason:** {reason or 'N/A'}",
                color=0x3B82F6
            )
            embed.set_footer(text=f"Server: {interaction.guild.name}")
            await interaction.user.send(embed=embed)
        except discord.Forbidden:
            pass

        embed = BotEmbed.success("Leave Started", f"You are now on leave until {end}. The {role.mention} role has been assigned.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def end_leave_early(self, interaction: discord.Interaction):
        """Manually end an active leave."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM leaves WHERE guild_id=? AND user_id=? AND active=1", (interaction.guild_id, interaction.user.id))
            leave = await cursor.fetchone()
            if not leave:
                embed = BotEmbed.error("No Active Leave", "You do not have an active leave.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Process the end of leave (common function)
        await self.process_leave_end(interaction.guild, interaction.user, leave, early=True)
        embed = BotEmbed.success("Leave Ended", "Your leave has been ended. The role has been removed.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def process_leave_end(self, guild: discord.Guild, member: discord.Member, leave_row, early: bool = False):
        """Common logic to end a leave: calculate days, update stats, remove role, DM."""
        start = date.fromisoformat(leave_row["start_date"])
        end = date.fromisoformat(leave_row["end_date"])
        # Use today as end if early, otherwise the planned end date
        actual_end = date.today() if early else max(end, date.today())  # if auto-ended, it's already past end
        days = (actual_end - start).days + 1  # inclusive

        # Mark leave inactive
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE leaves SET active=0 WHERE id=?", (leave_row["id"],))
            await db.commit()

        # Add leave days to staff stats
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO staff_stats (guild_id, user_id, tickets_claimed, tickets_closed, leave_days) VALUES (?,?,0,0,?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET leave_days = leave_days + ?",
                (guild.id, member.id, days, days)
            )
            await db.commit()

        # Remove leave role
        role_id = await self.get_leave_role(guild.id)
        if role_id:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Leave ended")
                except discord.Forbidden:
                    pass

        # DM the user
        try:
            embed = discord.Embed(
                title="🔔 Leave Ended",
                description=f"Your leave ({start} to {end}) has ended. Welcome back!",
                color=0x3B82F6
            )
            embed.add_field(name="Days counted", value=str(days))
            embed.set_footer(text=f"Server: {guild.name}")
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

    # ---------- Background task: auto-end expired leaves ----------
    @tasks.loop(hours=6)
    async def check_leaves(self):
        await self.bot.wait_until_ready()
        today = date.today().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM leaves WHERE active=1 AND end_date < ?", (today,))
            expired_leaves = await cursor.fetchall()

        for leave in expired_leaves:
            guild = self.bot.get_guild(leave["guild_id"])
            if not guild:
                continue
            member = guild.get_member(leave["user_id"])
            if not member:
                continue
            await self.process_leave_end(guild, member, leave, early=False)

    @check_leaves.before_loop
    async def before_check_leaves(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leave_settings (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reason TEXT DEFAULT '',
                active INTEGER DEFAULT 1
            )
        """)
        # Add leave_days column to staff_stats if not exists
        try:
            await db.execute("ALTER TABLE staff_stats ADD COLUMN leave_days INTEGER DEFAULT 0")
        except:
            pass
        await db.commit()
    await bot.add_cog(Leave(bot))