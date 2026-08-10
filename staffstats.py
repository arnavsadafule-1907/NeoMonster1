import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import ticket_staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class StaffStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
                    "claimed": row["tickets_claimed"],
                    "closed": row["tickets_closed"],
                    "leave_days": row["leave_days"] or 0
                }
            return {"claimed": 0, "closed": 0, "leave_days": 0}

    @staticmethod
    async def is_on_leave(guild_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM leaves WHERE guild_id=? AND user_id=? AND active=1", (guild_id, user_id))
            return await cursor.fetchone() is not None


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
        # Add leave_days column if not exists (for existing tables)
        try:
            await db.execute("ALTER TABLE staff_stats ADD COLUMN leave_days INTEGER DEFAULT 0")
        except:
            pass
        await db.commit()
    await bot.add_cog(StaffStats(bot))