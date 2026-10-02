import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiosqlite
import os
from datetime import datetime, timezone
from formatter import BotEmbed
from checks import is_extra_owner

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

running_campaigns = {}


class DMAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    class ConfirmView(discord.ui.View):
        def __init__(self, cog, embed, guild, author):
            super().__init__(timeout=30)
            self.cog = cog
            self.embed = embed
            self.guild = guild
            self.author = author
            self.value = None

        @discord.ui.button(label="✅ Yes, send to everyone", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("This is not your command.", ephemeral=True)
                return
            self.value = True
            self.stop()
            await interaction.response.edit_message(view=None)
            await self.cog.start_campaign(interaction, self.guild, self.embed)

        @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("This is not your command.", ephemeral=True)
                return
            self.value = False
            self.stop()
            await interaction.response.edit_message(view=None)

    @app_commands.command(name="dmall", description="Send an embed to every member in the server")
    @app_commands.describe(
        title="Embed title",
        description="Embed description",
        color="Hex color (e.g., #3B82F6)",
        image_url="Image URL (optional)",
        thumbnail_url="Thumbnail URL (optional)",
        footer="Footer text (optional)"
    )
    async def dmall(self, interaction: discord.Interaction,
                    title: str, description: str, color: str = None,
                    image_url: str = None, thumbnail_url: str = None, footer: str = None):
        if interaction.user.id != interaction.guild.owner_id:
            if not await is_extra_owner(interaction.guild_id, interaction.user.id):
                embed = BotEmbed.error("Permission Denied", "Only the server owner or extra owners can use this.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed_color = discord.Color.blue()
        if color:
            try:
                embed_color = discord.Color.from_str(color)
            except:
                embed = BotEmbed.error("Invalid Color", f"`{color}` is not a valid hex color.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        dm_embed = discord.Embed(title=title, description=description, color=embed_color)
        if image_url:
            dm_embed.set_image(url=image_url)
        if thumbnail_url:
            dm_embed.set_thumbnail(url=thumbnail_url)
        if footer:
            dm_embed.set_footer(text=footer)

        confirm_view = self.ConfirmView(self, dm_embed, interaction.guild, interaction.user)
        await interaction.response.send_message(
            "Are you sure you want to send this embed to **every member**?",
            embed=dm_embed,
            view=confirm_view,
            ephemeral=True
        )
        await confirm_view.wait()
        if confirm_view.value is None:
            await interaction.edit_original_response(content="Timed out.", embed=None, view=None)

    async def start_campaign(self, interaction: discord.Interaction, guild: discord.Guild, embed: discord.Embed):
        members = [m for m in guild.members if not m.bot]
        total = len(members)

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO dm_campaigns (guild_id, initiator_id, title, description, total, sent, failed, status, started_at) "
                "VALUES (?, ?, ?, ?, ?, 0, 0, 'running', ?)",
                (guild.id, interaction.user.id, embed.title, embed.description, total,
                 datetime.now(timezone.utc).isoformat())
            )
            campaign_id = cursor.lastrowid
            await db.commit()

        status_msg = await interaction.followup.send(f"📤 Sending DMs… (0/{total})", ephemeral=True)
        running_campaigns[campaign_id] = {"cancel": False}
        asyncio.create_task(self._send_loop(campaign_id, members, embed, status_msg, guild.id))

    async def _send_loop(self, campaign_id, members, embed, status_msg, guild_id):
        sent = 0
        failed = 0
        total = len(members)

        try:
            for i, member in enumerate(members):
                if running_campaigns.get(campaign_id, {}).get("cancel"):
                    await self._update_campaign(campaign_id, sent, failed, "cancelled")
                    await status_msg.edit(content=f"🛑 Campaign cancelled. Sent: {sent}, Failed: {failed}")
                    return

                try:
                    await member.send(embed=embed)
                    sent += 1
                except discord.Forbidden:
                    failed += 1
                except Exception:
                    failed += 1

                if (i + 1) % 10 == 0:
                    await status_msg.edit(content=f"📤 Sending DMs… ({i+1}/{total})")
                    await self._update_campaign(campaign_id, sent, failed, "running")

                await asyncio.sleep(0.5)

            await self._update_campaign(campaign_id, sent, failed, "completed")
            result = BotEmbed.success("DM All Completed", f"**Sent:** {sent}\n**Failed:** {failed}")
            await status_msg.edit(content=None, embed=result)

        except Exception as e:
            await self._update_campaign(campaign_id, sent, failed, "failed")
            await status_msg.edit(content=f"❌ Campaign failed: {e}")
        finally:
            running_campaigns.pop(campaign_id, None)

    async def _update_campaign(self, campaign_id, sent, failed, status):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE dm_campaigns SET sent = ?, failed = ?, status = ?, completed_at = ? WHERE id = ?",
                (sent, failed, status, datetime.now(timezone.utc).isoformat(), campaign_id)
            )
            await db.commit()

    @app_commands.command(name="dmstatus", description="Show the status of the current or latest DM campaign")
    async def dmstatus(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM dm_campaigns WHERE guild_id = ? ORDER BY id DESC LIMIT 1",
                (interaction.guild_id,)
            )
            row = await cursor.fetchone()

        if not row:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Campaigns", "No DM campaigns found."),
                ephemeral=True
            )

        embed = discord.Embed(title="📊 DM Campaign Status", color=0x3B82F6)
        embed.add_field(name="Campaign ID", value=str(row["id"]), inline=True)
        embed.add_field(name="Initiator", value=f"<@{row['initiator_id']}>", inline=True)
        embed.add_field(name="Status", value=row["status"].capitalize(), inline=True)
        embed.add_field(name="Total", value=str(row["total"]), inline=True)
        embed.add_field(name="Sent", value=str(row["sent"]), inline=True)
        embed.add_field(name="Failed", value=str(row["failed"]), inline=True)
        embed.add_field(name="Started", value=row["started_at"][:19].replace("T", " "), inline=True)
        if row["completed_at"]:
            embed.add_field(name="Completed", value=row["completed_at"][:19].replace("T", " "), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="dmcancel", description="Cancel the currently running DM campaign")
    async def dmcancel(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            if not await is_extra_owner(interaction.guild_id, interaction.user.id):
                return await interaction.response.send_message(
                    embed=BotEmbed.error("Permission Denied", "Only the server owner or extra owners can cancel."),
                    ephemeral=True
                )

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id FROM dm_campaigns WHERE guild_id = ? AND status = 'running' ORDER BY id DESC LIMIT 1",
                (interaction.guild_id,)
            )
            row = await cursor.fetchone()

        if not row:
            return await interaction.response.send_message(
                embed=BotEmbed.info("No Running Campaign", "There is no running DM campaign."),
                ephemeral=True
            )

        campaign_id = row["id"]
        if campaign_id in running_campaigns:
            running_campaigns[campaign_id]["cancel"] = True
            await interaction.response.send_message(
                embed=BotEmbed.success("Cancelling", "The DM campaign is being cancelled."),
                ephemeral=True
            )
        else:
            await self._update_campaign(campaign_id, 0, 0, "cancelled")
            await interaction.response.send_message(
                embed=BotEmbed.success("Cancelled", "The campaign was already stopped."),
                ephemeral=True
            )


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dm_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                initiator_id INTEGER NOT NULL,
                title TEXT,
                description TEXT,
                total INTEGER DEFAULT 0,
                sent INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                started_at TEXT,
                completed_at TEXT
            )
        """)
        await db.commit()
    await bot.add_cog(DMAll(bot))