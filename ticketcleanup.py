import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class TicketCleanup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="cleanuptickets", description="Delete all ticket channels that are not in the database (admin only)")
    @admin_only()
    async def cleanup_tickets(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        deleted = 0
        failed = 0

        # Get all ticket channel IDs from the database
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT channel_id FROM ticket_metadata")
            rows = await cursor.fetchall()
            valid_channel_ids = {row[0] for row in rows}

        # Also check ticket_metadata table exists; if not, we treat all as orphaned
        # But we'll assume it exists.

        # Find channels that look like tickets (name starts with "ticket-" or "claimed-")
        # Optionally, restrict to a specific category if you have one configured.
        # For safety, we'll only delete channels that start with "ticket-" or "claimed-".
        for channel in guild.channels:
            if not isinstance(channel, discord.TextChannel):
                continue
            if not (channel.name.startswith("ticket-") or channel.name.startswith("claimed-")):
                continue

            if channel.id in valid_channel_ids:
                continue  # This ticket is still in the DB – keep it.

            # Orphaned – delete it
            try:
                await channel.delete(reason="Orphaned ticket cleanup")
                deleted += 1
            except Exception as e:
                failed += 1

        embed = BotEmbed.success(
            "🧹 Ticket Cleanup Complete",
            f"Deleted **{deleted}** orphaned ticket channels.\n"
            f"Failed to delete **{failed}** (check bot permissions)."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TicketCleanup(bot))