import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import re
from formatter import BotEmbed
from checks import ticket_staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# Column name mapping for reset/add stats
STAT_COLUMN_MAP = {
    "claimed": "tickets_claimed",
    "closed": "tickets_closed",
    "leavedays": "leave_days",
}

class StaffStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Permission check for admin commands ----------
    async def is_admin_allowed(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        return False

    # ---------- Helper to convert string to member ----------
    async def convert_to_member(self, interaction: discord.Interaction, user_str: str) -> discord.Member | None:
        guild = interaction.guild
        user_str = user_str.strip()

        if user_str.isdigit():
            return guild.get_member(int(user_str))

        mention_match = re.match(r'<@!?(\d+)>', user_str)
        if mention_match:
            return guild.get_member(int(mention_match.group(1)))

        member = discord.utils.get(guild.members, name=user_str)
        if member:
            return member

        member = discord.utils.get(guild.members, display_name=user_str)
        if member:
            return member

        member = discord.utils.get(guild.members, nick=user_str)
        if member:
            return member

        return None

    # ---------- Ensure staff_stats row exists ----------
    async def ensure_staff_stats(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO staff_stats (guild_id, user_id, tickets_claimed, tickets_closed, leave_days) VALUES (?, ?, 0, 0, 0)",
                (guild_id, user_id)
            )
            await db.commit()

    # ---------- Staff stats view command ----------
    @app_commands.command(name="staffstats", description="View ticket statistics and leave days for a staff member")
    @app_commands.describe(user="Staff member to check (default: yourself)")
    @ticket_staff_only()
    async def staffstats(self, interaction: discord.Interaction, user: discord.Member = None):
        if user is None:
            user = interaction.user

        stats = await self.get_staff_stats(interaction.guild_id, user.id)
        on_leave = await self.is_on_leave(interaction.guild_id, user.id)

        embed = discord.Embed(
            title=f"📊 Staff Statistics – {user.display_name}",
            color=0x3B82F6,
            timestamp=interaction.created_at
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="🎫 Tickets Claimed", value=f"`{stats['claimed']}`", inline=True)
        embed.add_field(name="🔒 Tickets Closed", value=f"`{stats['closed']}`", inline=True)
        embed.add_field(name="📋 Total Handled", value=f"`{stats['claimed'] + stats['closed']}`", inline=True)
        embed.add_field(name="🏖️ Leave Days Taken", value=f"`{stats['leave_days']}`", inline=True)
        embed.add_field(name="📅 Currently on Leave", value="`Yes`" if on_leave else "`No`", inline=True)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed, ephemeral=False)

    # ---------- Add stat command ----------
    @app_commands.command(name="addstaffstats", description="Add to a staff member's statistics (owner only)")
    @app_commands.describe(
        user="Staff member to add stats to",
        stat="Which stat to add to",
        amount="Amount to add (positive integer)",
    )
    @app_commands.choices(stat=[
        app_commands.Choice(name="claimed", value="claimed"),
        app_commands.Choice(name="closed", value="closed"),
        app_commands.Choice(name="leavedays", value="leavedays"),
    ])
    async def add_staff_stats(
        self,
        interaction: discord.Interaction,
        user: str,
        stat: str,
        amount: int = 1
    ):
        # Permission check
        if not await self.is_admin_allowed(interaction):
            embed = BotEmbed.error(
                "Permission Denied",
                "Only the server owner or bot owner can add to staff statistics."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Validate amount
        if amount <= 0:
            embed = BotEmbed.error("Invalid Amount", "Amount must be a positive integer.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Convert user string to Member
        target_user = await self.convert_to_member(interaction, user)
        if target_user is None:
            embed = BotEmbed.error(
                "Invalid User",
                "Could not find that user. Please mention a valid member or use their ID."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Map stat to column name
        column = STAT_COLUMN_MAP.get(stat)
        if not column:
            embed = BotEmbed.error("Invalid Stat", f"Unknown stat: {stat}")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Ensure a row exists for this user
        await self.ensure_staff_stats(interaction.guild_id, target_user.id)

        # Update the stat
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                f"UPDATE staff_stats SET {column} = {column} + ? WHERE guild_id = ? AND user_id = ?",
                (amount, interaction.guild_id, target_user.id)
            )
            await db.commit()

        # Get the new value for confirmation
        new_stats = await self.get_staff_stats(interaction.guild_id, target_user.id)

        stat_names = {
            "claimed": "Tickets Claimed",
            "closed": "Tickets Closed",
            "leavedays": "Leave Days",
        }

        embed = BotEmbed.success(
            "✅ Stats Updated",
            f"Added **{amount}** to **{stat_names.get(stat, stat)}** for {target_user.mention}.\n"
            f"**New total:** `{new_stats[stat]}`"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Reset command ----------
    @app_commands.command(name="resetstaffstats", description="Reset staff statistics (owner only)")
    @app_commands.describe(
        user="Staff member to reset (or 'all' for everyone)",
        stat="Which stat to reset: claimed, closed, leavedays, or all",
    )
    @app_commands.choices(stat=[
        app_commands.Choice(name="claimed", value="claimed"),
        app_commands.Choice(name="closed", value="closed"),
        app_commands.Choice(name="leavedays", value="leavedays"),
        app_commands.Choice(name="all", value="all"),
    ])
    async def reset_staff_stats(
        self,
        interaction: discord.Interaction,
        user: str,
        stat: str
    ):
        if not await self.is_admin_allowed(interaction):
            embed = BotEmbed.error(
                "Permission Denied",
                "Only the server owner or bot owner can reset staff statistics."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if user.lower() == "all":
            embed = discord.Embed(
                title="⚠️ Confirm Reset All",
                description=(
                    f"Are you sure you want to reset **{stat}** for **all staff members**?\n"
                    "This action **cannot** be undone."
                ),
                color=discord.Color.red()
            )
            view = ConfirmResetView(self, interaction.guild_id, stat, None)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        target_user = await self.convert_to_member(interaction, user)
        if target_user is None:
            embed = BotEmbed.error(
                "Invalid User",
                "Could not find that user. Please mention a valid member, use their ID, or use `all`."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description=(
                f"Are you sure you want to reset **{stat}** for **{target_user.mention}**?\n"
                "This action **cannot** be undone."
            ),
            color=discord.Color.red()
        )
        view = ConfirmResetView(self, interaction.guild_id, stat, target_user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ---------- Actual reset logic ----------
    async def execute_reset(self, interaction: discord.Interaction, guild_id: int, stat: str, user_id: int = None):
        """Execute the reset after confirmation."""
        # Map stat to column name
        if stat == "all":
            columns = ["tickets_claimed", "tickets_closed", "leave_days"]
        else:
            column = STAT_COLUMN_MAP.get(stat)
            if not column:
                embed = BotEmbed.error("Invalid Stat", f"Unknown stat: {stat}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        async with aiosqlite.connect(DB_PATH) as db:
            if user_id is None:
                # Reset all staff in the guild
                if stat == "all":
                    await db.execute(
                        "UPDATE staff_stats SET tickets_claimed = 0, tickets_closed = 0, leave_days = 0 WHERE guild_id = ?",
                        (guild_id,)
                    )
                else:
                    await db.execute(
                        f"UPDATE staff_stats SET {column} = 0 WHERE guild_id = ?",
                        (guild_id,)
                    )
            else:
                # Reset individual staff
                if stat == "all":
                    await db.execute(
                        "UPDATE staff_stats SET tickets_claimed = 0, tickets_closed = 0, leave_days = 0 WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id)
                    )
                else:
                    await db.execute(
                        f"UPDATE staff_stats SET {column} = 0 WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id)
                    )
            await db.commit()

        if user_id is None:
            target_desc = "**all staff members**"
        else:
            member = interaction.guild.get_member(user_id)
            target_desc = f"{member.mention if member else f'User {user_id}'}"

        stat_names = {
            "claimed": "Tickets Claimed",
            "closed": "Tickets Closed",
            "leavedays": "Leave Days",
            "all": "All Statistics"
        }

        embed = BotEmbed.success(
            "✅ Reset Complete",
            f"**{stat_names.get(stat, stat)}** have been reset for {target_desc}."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- Helper methods ----------
    @staticmethod
    async def get_staff_stats(guild_id: int, user_id: int) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT tickets_claimed, tickets_closed, leave_days FROM staff_stats WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "claimed": row["tickets_claimed"] or 0,
                    "closed": row["tickets_closed"] or 0,
                    "leave_days": row["leave_days"] or 0
                }
            return {"claimed": 0, "closed": 0, "leave_days": 0}

    @staticmethod
    async def is_on_leave(guild_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM leaves WHERE guild_id=? AND user_id=? AND active=1", (guild_id, user_id))
            return await cursor.fetchone() is not None


# ---------- Confirmation View ----------
class ConfirmResetView(discord.ui.View):
    def __init__(self, cog, guild_id: int, stat: str, user_id: int = None):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.stat = stat
        self.user_id = user_id

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.execute_reset(interaction, self.guild_id, self.stat, self.user_id)
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = BotEmbed.info("Cancelled", "Reset action has been cancelled.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS staff_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tickets_claimed INTEGER DEFAULT 0,
                tickets_closed INTEGER DEFAULT 0,
                leave_days INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        try:
            await db.execute("ALTER TABLE staff_stats ADD COLUMN leave_days INTEGER DEFAULT 0")
        except:
            pass
        await db.commit()
    await bot.add_cog(StaffStats(bot))