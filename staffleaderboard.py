import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import ticket_staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class StaffLeaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="staffleaderboard", description="View the staff leaderboard based on ticket activity")
    @app_commands.describe(period="Time period to show (all-time, monthly, weekly)")
    @app_commands.choices(period=[
        app_commands.Choice(name="All-Time", value="all"),
        app_commands.Choice(name="Monthly", value="month"),
        app_commands.Choice(name="Weekly", value="week"),
    ])
    @ticket_staff_only()
    async def staffleaderboard(self, interaction: discord.Interaction, period: str = "all"):
        await interaction.response.defer(thinking=True)

        # Build the query based on period
        # The staff_stats table currently doesn't have timestamps for each action, so we only have total counts.
        # For "all-time", we use total counts. For monthly/weekly, we'd need timestamps – we can add them later.
        # For now, we'll just show all-time and note that period filtering is coming soon.
        if period != "all":
            embed = BotEmbed.info(
                "⏳ Coming Soon",
                "Monthly and weekly filtering will be available after we add timestamps to staff actions.\n"
                "For now, showing **all-time** leaderboard."
            )
            # Still show all-time data
            period = "all"

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT 
                    user_id,
                    tickets_claimed,
                    tickets_closed,
                    tickets_claimed + tickets_closed as total_handled,
                    leave_days
                FROM staff_stats
                WHERE guild_id = ?
                ORDER BY total_handled DESC, tickets_claimed DESC
                LIMIT 15
            """, (interaction.guild_id,))
            rows = await cursor.fetchall()

        if not rows:
            embed = BotEmbed.info(
                "No Staff Activity",
                "No ticket activity has been recorded yet. Staff will appear here once they start handling tickets."
            )
            return await interaction.followup.send(embed=embed)

        # Build leaderboard embed
        embed = discord.Embed(
            title="🏆 Staff Leaderboard",
            description="Staff ranked by tickets handled (claimed + closed).",
            color=0x3B82F6,
            timestamp=interaction.created_at
        )
        embed.set_footer(text="DesireSmp • Staff Stats")

        medal_emojis = ["🥇", "🥈", "🥉"]

        for idx, row in enumerate(rows):
            user_id = row["user_id"]
            claimed = row["tickets_claimed"] or 0
            closed = row["tickets_closed"] or 0
            total = row["total_handled"] or 0
            leave_days = row["leave_days"] or 0

            # Try to get member display name, fallback to user ID
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"

            medal = medal_emojis[idx] if idx < 3 else f"{idx+1}."
            value = f"**Claimed:** {claimed}  •  **Closed:** {closed}  •  **Leave Days:** {leave_days}"
            embed.add_field(
                name=f"{medal} {name} (Total: {total})",
                value=value,
                inline=False
            )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StaffLeaderboard(bot))