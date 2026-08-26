import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from datetime import datetime, timezone
from formatter import BotEmbed
from checks import owner_only  # <-- new import

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class TicketCleanup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- 1. Delete orphaned tickets (not in metadata) ----------
    @app_commands.command(name="cleanuptickets", description="Delete orphaned ticket channels (not in DB) – owner only")
    @owner_only()   # <-- changed from admin_only
    async def cleanup_orphaned(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        deleted = 0
        failed = 0

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT channel_id FROM ticket_metadata")
            rows = await cursor.fetchall()
            valid_ids = {row[0] for row in rows}

        for channel in guild.channels:
            if not isinstance(channel, discord.TextChannel):
                continue
            if not (channel.name.startswith("ticket-") or channel.name.startswith("claimed-")):
                continue
            if channel.id in valid_ids:
                continue

            try:
                await channel.delete(reason="Orphaned ticket cleanup")
                deleted += 1
            except:
                failed += 1

        embed = BotEmbed.success(
            "🧹 Orphaned Tickets Cleaned",
            f"Deleted **{deleted}** orphaned ticket channels.\nFailed: **{failed}**"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---------- 2. Close all active tickets (in metadata) ----------
    @app_commands.command(name="closealltickets", description="Close ALL active tickets (delete channels & metadata) – owner only")
    @owner_only()   # <-- changed from admin_only
    async def close_all_tickets(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Confirm Mass Ticket Closure",
            description="This will **permanently delete** all active ticket channels and remove their metadata.\n"
                        "This action **cannot** be undone.\n\n"
                        "React with ✅ to confirm, or ❌ to cancel.",
            color=discord.Color.red()
        )
        view = ConfirmCloseView(self, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _execute_close_all(self, interaction: discord.Interaction, guild: discord.Guild):
        closed = 0
        failed = 0

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_metadata")
            tickets = await cursor.fetchall()

            for ticket in tickets:
                channel_id = ticket["channel_id"]
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.delete(reason="Mass ticket closure")
                        await db.execute("DELETE FROM ticket_metadata WHERE channel_id = ?", (channel_id,))
                        await db.commit()
                        closed += 1
                    except:
                        failed += 1
                else:
                    await db.execute("DELETE FROM ticket_metadata WHERE channel_id = ?", (channel_id,))
                    await db.commit()
                    closed += 1

        embed = BotEmbed.success(
            "🧹 All Active Tickets Closed",
            f"Closed **{closed}** active ticket channels.\nFailed: **{failed}**"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


# ---------- Confirmation view ----------
class ConfirmCloseView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog._execute_close_all(interaction, self.guild)
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = BotEmbed.info("Cancelled", "Mass ticket closure cancelled.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)


async def setup(bot):
    await bot.add_cog(TicketCleanup(bot))