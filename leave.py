import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import os
from datetime import date, datetime
from formatter import BotEmbed
from checks import ticket_staff_only, admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# ---------- Persistent Leave Panel View ----------
class LeavePanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Request Leave", style=discord.ButtonStyle.primary, custom_id="leave_take")
    async def take_leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.cog._check_staff(interaction):
            return
        await interaction.response.send_modal(LeaveModal(self.cog))

    @discord.ui.button(label="End Leave", style=discord.ButtonStyle.success, custom_id="leave_return")
    async def return_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.cog._check_staff(interaction):
            return
        await self.cog.end_leave_early(interaction)


# ---------- Modal for Requesting Leave ----------
class LeaveModal(discord.ui.Modal, title="Request Leave"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.start_date = discord.ui.TextInput(
            label="Start Date (YYYY-MM-DD)",
            placeholder="e.g., 2026-08-15",
            required=True,
            max_length=10
        )
        self.add_item(self.start_date)
        self.end_date = discord.ui.TextInput(
            label="End Date (YYYY-MM-DD)",
            placeholder="e.g., 2026-08-20",
            required=True,
            max_length=10
        )
        self.add_item(self.end_date)
        self.reason = discord.ui.TextInput(
            label="Reason (optional)",
            placeholder="Briefly state the purpose of your leave",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.start_leave(interaction, self.start_date.value, self.end_date.value, self.reason.value)


# ---------- Leave Cog ----------
class Leave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_leaves.start()

    def cog_unload(self):
        self.check_leaves.cancel()

    async def _check_staff(self, interaction: discord.Interaction) -> bool:
        allowed_roles = ["TicketSupporter", "Staff.exe", "admin.exe", "nuke.exe"]
        for role_name in allowed_roles:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in interaction.user.roles:
                return True
        if interaction.user.id == interaction.guild.owner_id or interaction.user.id in interaction.client.owner_ids:
            return True
        await interaction.response.send_message(
            embed=BotEmbed.error("Permission Denied", "You do not have permission to manage leaves."),
            ephemeral=True
        )
        return False

    async def get_leave_role(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT role_id FROM leave_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_leave_role(self, guild_id: int, role_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO leave_settings (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
            await db.commit()

    # ---------- /leavepanel (admin only) ----------
    @app_commands.command(name="leavepanel", description="Display the staff leave management panel")
    @admin_only()
    async def leave_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Staff Leave Management",
            description="Use the buttons below to request a leave or to return to duty.",
            color=0x3B82F6
        )
        embed.add_field(name="Request Leave", value="Submit your leave dates and reason.", inline=False)
        embed.add_field(name="End Leave", value="Manually end an active leave and resume work.", inline=False)
        embed.set_footer(text="NeoMonster • Leave System")

        view = LeavePanelView(self)
        await interaction.response.send_message(embed=embed, view=view)

    # ---------- /leavesetup (admin only) ----------
    @app_commands.command(name="leavesetup", description="Configure the role assigned to staff on leave")
    @app_commands.describe(role="The role to be given during leave (should have no extra permissions)")
    @admin_only()
    async def leave_setup(self, interaction: discord.Interaction, role: discord.Role):
        await self.set_leave_role(interaction.guild_id, role.id)
        embed = BotEmbed.success("Leave Role Configured", f"The {role.mention} role will now be assigned to staff on leave.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /leave slash command ----------
    @app_commands.command(name="leave", description="Manage your leave status")
    @app_commands.describe(action="Request or end a leave", start_date="Start date (YYYY-MM-DD)", end_date="End date (YYYY-MM-DD)", reason="Reason for leave")
    @app_commands.choices(action=[
        app_commands.Choice(name="Request Leave", value="take"),
        app_commands.Choice(name="End Leave", value="return"),
    ])
    @ticket_staff_only()
    async def leave_cmd(self, interaction: discord.Interaction, action: str, start_date: str = None, end_date: str = None, reason: str = None):
        if action == "take":
            await self.start_leave(interaction, start_date, end_date, reason)
        elif action == "return":
            await self.end_leave_early(interaction)

    async def start_leave(self, interaction: discord.Interaction, start_str: str, end_str: str, reason: str):
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            embed = BotEmbed.error("Invalid Date", "Please use the format `YYYY-MM-DD`.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if start > end:
            embed = BotEmbed.error("Invalid Dates", "Start date must not be after end date.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if start < date.today():
            embed = BotEmbed.error("Invalid Date", "Start date cannot be in the past.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT id FROM leaves WHERE guild_id=? AND user_id=? AND active=1", (interaction.guild_id, interaction.user.id))
            if await cursor.fetchone():
                embed = BotEmbed.error("Leave Already Active", "You are already on leave. Use the End Leave button to return.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        role_id = await self.get_leave_role(interaction.guild_id)
        if not role_id:
            embed = BotEmbed.error("Not Configured", "A server administrator must first set the leave role with `/leavesetup`.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        role = interaction.guild.get_role(role_id)
        if not role:
            embed = BotEmbed.error("Configuration Error", "The configured leave role no longer exists. Please contact an administrator.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            await interaction.user.add_roles(role, reason="Staff leave")
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Error", "I do not have permission to assign this role. Please check role hierarchy.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO leaves (guild_id, user_id, start_date, end_date, reason, active) VALUES (?,?,?,?,?,1)",
                (interaction.guild_id, interaction.user.id, start.isoformat(), end.isoformat(), reason or "")
            )
            await db.commit()

        try:
            embed = discord.Embed(
                title="Leave Approved",
                description=f"Your leave has been registered.\n**Start:** {start}\n**End:** {end}\n**Reason:** {reason or 'N/A'}",
                color=0x3B82F6
            )
            embed.set_footer(text=f"Server: {interaction.guild.name}")
            await interaction.user.send(embed=embed)
        except discord.Forbidden:
            pass

        embed = BotEmbed.success("Leave Started", f"You are now on leave until **{end}**. The {role.mention} role has been assigned.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def end_leave_early(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM leaves WHERE guild_id=? AND user_id=? AND active=1", (interaction.guild_id, interaction.user.id))
            leave = await cursor.fetchone()
            if not leave:
                embed = BotEmbed.error("No Active Leave", "You do not have an active leave to end.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        await self.process_leave_end(interaction.guild, interaction.user, leave, early=True)
        embed = BotEmbed.success("Leave Ended", "Your leave has been ended. The leave role has been removed and your return has been logged.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def process_leave_end(self, guild: discord.Guild, member: discord.Member, leave_row, early: bool = False):
        start = date.fromisoformat(leave_row["start_date"])
        end = date.fromisoformat(leave_row["end_date"])
        actual_end = date.today() if early else max(end, date.today())
        days = (actual_end - start).days + 1

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE leaves SET active=0 WHERE id=?", (leave_row["id"],))
            await db.commit()

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO staff_stats (guild_id, user_id, tickets_claimed, tickets_closed, leave_days) VALUES (?,?,0,0,?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET leave_days = leave_days + ?",
                (guild.id, member.id, days, days)
            )
            await db.commit()

        role_id = await self.get_leave_role(guild.id)
        if role_id:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Leave ended")
                except discord.Forbidden:
                    pass

        try:
            embed = discord.Embed(
                title="Leave Concluded",
                description=f"Your leave period ({start} to {end}) has ended. Welcome back!",
                color=0x3B82F6
            )
            embed.add_field(name="Days Counted", value=str(days))
            embed.set_footer(text=f"Server: {guild.name}")
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

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
        try:
            await db.execute("ALTER TABLE staff_stats ADD COLUMN leave_days INTEGER DEFAULT 0")
        except:
            pass
        await db.commit()
    await bot.add_cog(Leave(bot))