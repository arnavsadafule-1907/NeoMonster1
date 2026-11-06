import os
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only, is_extra_owner
from formatter import BotEmbed

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

STAT_NAMES = {
    "claimed": "Tickets Claimed",
    "closed": "Tickets Closed",
    "leavedays": "Leave Days",
}


class ConfirmResetView(discord.ui.View):
    def __init__(self, cog, guild_id: int, user_id: int | None, stat: str, display_target: str, display_stat: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.stat = stat
        self.display_target = display_target
        self.display_stat = display_stat

    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.execute_reset(interaction, self.guild_id, self.user_id, self.stat)
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        cancel_icon = "❌"
        await interaction.response.edit_message(
            content=f"{cancel_icon} Reset cancelled.",
            embed=None,
            view=self
        )


class StaffStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _ensure_tables(self):
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
            await db.commit()

    async def ensure_staff_stats(self, guild_id: int, user_id: int):
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO staff_stats (guild_id, user_id, tickets_claimed, tickets_closed, leave_days) VALUES (?, ?, 0, 0, 0)",
                (guild_id, user_id)
            )
            await db.commit()

    async def get_staff_stats(self, guild_id: int, user_id: int):
        await self.ensure_staff_stats(guild_id, user_id)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT tickets_claimed, tickets_closed, leave_days FROM staff_stats WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            return await cursor.fetchone()

    staffstats_group = app_commands.Group(name="staffstats", description="Manage and view staff performance statistics")

    @staffstats_group.command(name="view", description="View a staff member's ticket and leave statistics")
    @app_commands.describe(user="Staff member to inspect (defaults to you)")
    async def view_stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target_user = user or interaction.user
        stats = await self.get_staff_stats(interaction.guild_id, target_user.id)

        claimed = stats["tickets_claimed"] if stats else 0
        closed = stats["tickets_closed"] if stats else 0
        leave_days = stats["leave_days"] if stats else 0
        total_handled = claimed + closed

        embed = discord.Embed(
            title=f"Staff Stats — {target_user.display_name}",
            color=0x3B82F6,
            timestamp=interaction.created_at
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="Tickets Claimed", value=f"**{claimed}**", inline=True)
        embed.add_field(name="Tickets Closed", value=f"**{closed}**", inline=True)
        embed.add_field(name="Total Handled", value=f"**{total_handled}**", inline=True)
        embed.add_field(name="Leave Days Taken", value=f"**{leave_days}** days", inline=True)
        embed.set_footer(text=f"User ID: {target_user.id}")

        await interaction.response.send_message(embed=embed)

    @staffstats_group.command(name="add", description="Add to a staff member's statistics (Admin only)")
    @app_commands.describe(
        user="Staff member to update",
        stat="Which statistic to increase",
        amount="Amount to add (positive number)"
    )
    @app_commands.choices(stat=[
        app_commands.Choice(name="Tickets Claimed", value="claimed"),
        app_commands.Choice(name="Tickets Closed", value="closed"),
        app_commands.Choice(name="Leave Days", value="leavedays"),
    ])
    @admin_only()
    async def add_stat(self, interaction: discord.Interaction, user: discord.Member, stat: str, amount: int):
        if amount <= 0:
            embed = BotEmbed.error("Invalid Amount", "The amount must be a positive number.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await self.ensure_staff_stats(interaction.guild_id, user.id)

        async with aiosqlite.connect(DB_PATH) as db:
            if stat == "claimed":
                await db.execute(
                    "UPDATE staff_stats SET tickets_claimed = tickets_claimed + ? WHERE guild_id = ? AND user_id = ?",
                    (amount, interaction.guild_id, user.id)
                )
            elif stat == "closed":
                await db.execute(
                    "UPDATE staff_stats SET tickets_closed = tickets_closed + ? WHERE guild_id = ? AND user_id = ?",
                    (amount, interaction.guild_id, user.id)
                )
            elif stat == "leavedays":
                await db.execute(
                    "UPDATE staff_stats SET leave_days = leave_days + ? WHERE guild_id = ? AND user_id = ?",
                    (amount, interaction.guild_id, user.id)
                )
            await db.commit()

        new_stats = await self.get_staff_stats(interaction.guild_id, user.id)
        stat_name = STAT_NAMES.get(stat, stat)
        new_val = new_stats[{"claimed": "tickets_claimed", "closed": "tickets_closed", "leavedays": "leave_days"}[stat]]

        embed = BotEmbed.success(
            "Stats Updated",
            f"Added **{amount}** to **{stat_name}** for {user.mention}.\nNew total: **{new_val}**"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staffstats_group.command(name="remove", description="Subtract from a staff member's statistics (Admin only)")
    @app_commands.describe(
        user="Staff member to update",
        stat="Which statistic to decrease",
        amount="Amount to subtract (positive number)"
    )
    @app_commands.choices(stat=[
        app_commands.Choice(name="Tickets Claimed", value="claimed"),
        app_commands.Choice(name="Tickets Closed", value="closed"),
        app_commands.Choice(name="Leave Days", value="leavedays"),
    ])
    @admin_only()
    async def remove_stat(self, interaction: discord.Interaction, user: discord.Member, stat: str, amount: int):
        if amount <= 0:
            embed = BotEmbed.error("Invalid Amount", "The amount must be a positive number.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await self.ensure_staff_stats(interaction.guild_id, user.id)

        async with aiosqlite.connect(DB_PATH) as db:
            if stat == "claimed":
                await db.execute(
                    "UPDATE staff_stats SET tickets_claimed = MAX(0, tickets_claimed - ?) WHERE guild_id = ? AND user_id = ?",
                    (amount, interaction.guild_id, user.id)
                )
            elif stat == "closed":
                await db.execute(
                    "UPDATE staff_stats SET tickets_closed = MAX(0, tickets_closed - ?) WHERE guild_id = ? AND user_id = ?",
                    (amount, interaction.guild_id, user.id)
                )
            elif stat == "leavedays":
                await db.execute(
                    "UPDATE staff_stats SET leave_days = MAX(0, leave_days - ?) WHERE guild_id = ? AND user_id = ?",
                    (amount, interaction.guild_id, user.id)
                )
            await db.commit()

        new_stats = await self.get_staff_stats(interaction.guild_id, user.id)
        stat_name = STAT_NAMES.get(stat, stat)
        new_val = new_stats[{"claimed": "tickets_claimed", "closed": "tickets_closed", "leavedays": "leave_days"}[stat]]

        embed = BotEmbed.success(
            "Stats Updated",
            f"Removed **{amount}** from **{stat_name}** for {user.mention}.\nNew total: **{new_val}**"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staffstats_group.command(name="reset", description="Reset statistics for a staff member or all staff (Owner only)")
    @app_commands.describe(
        stat="Which statistic to reset",
        user="Staff member to reset (omit to reset ALL staff)"
    )
    @app_commands.choices(stat=[
        app_commands.Choice(name="All Statistics", value="all"),
        app_commands.Choice(name="Tickets Claimed", value="claimed"),
        app_commands.Choice(name="Tickets Closed", value="closed"),
        app_commands.Choice(name="Leave Days", value="leavedays"),
    ])
    async def reset_stats(self, interaction: discord.Interaction, stat: str, user: discord.Member | None = None):
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id not in interaction.client.owner_ids:
            if not await is_extra_owner(interaction.guild_id, interaction.user.id):
                embed = BotEmbed.error("Permission Denied", "Only the server owner, extra owners, or bot owner can reset staff stats.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        target_desc = user.mention if user else "**all staff members**"
        stat_desc = "All Statistics" if stat == "all" else STAT_NAMES.get(stat, stat)

        embed = discord.Embed(
            title="Confirm Statistics Reset",
            description=(
                f"You are about to reset **{stat_desc}** for {target_desc}.\n"
                "This action cannot be undone. Click Confirm to proceed."
            ),
            color=discord.Color.red()
        )
        view = ConfirmResetView(self, interaction.guild_id, user.id if user else None, stat, target_desc, stat_desc)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def execute_reset(self, interaction: discord.Interaction, guild_id: int, user_id: int | None, stat: str):
        async with aiosqlite.connect(DB_PATH) as db:
            if user_id is None:
                if stat == "all":
                    await db.execute(
                        "UPDATE staff_stats SET tickets_claimed = 0, tickets_closed = 0, leave_days = 0 WHERE guild_id = ?",
                        (guild_id,)
                    )
                elif stat == "claimed":
                    await db.execute("UPDATE staff_stats SET tickets_claimed = 0 WHERE guild_id = ?", (guild_id,))
                elif stat == "closed":
                    await db.execute("UPDATE staff_stats SET tickets_closed = 0 WHERE guild_id = ?", (guild_id,))
                elif stat == "leavedays":
                    await db.execute("UPDATE staff_stats SET leave_days = 0 WHERE guild_id = ?", (guild_id,))
            else:
                if stat == "all":
                    await db.execute(
                        "UPDATE staff_stats SET tickets_claimed = 0, tickets_closed = 0, leave_days = 0 WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id)
                    )
                elif stat == "claimed":
                    await db.execute("UPDATE staff_stats SET tickets_claimed = 0 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
                elif stat == "closed":
                    await db.execute("UPDATE staff_stats SET tickets_closed = 0 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
                elif stat == "leavedays":
                    await db.execute("UPDATE staff_stats SET leave_days = 0 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()

        target_desc = f"<@{user_id}>" if user_id else "all staff members"
        stat_desc = "all statistics" if stat == "all" else STAT_NAMES.get(stat, stat)
        embed = BotEmbed.success(
            "Reset Complete",
            f"Successfully reset **{stat_desc}** for {target_desc}."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    cog = StaffStats(bot)
    await cog._ensure_tables()
    await bot.add_cog(cog)
