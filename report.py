import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
import traceback

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# -------------------------------------------------------------------
#  Report Modal (shared for both context menu and slash command)
# -------------------------------------------------------------------
class ReportModal(discord.ui.Modal, title="Report Message"):
    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message
        self.reason = discord.ui.TextInput(
            label="Reason for report",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000,
            placeholder="Explain what's wrong with this message"
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 1. Get the report channel for this guild
            channel_id = await self.get_report_channel(interaction.guild_id)
            if channel_id is None:
                await interaction.response.send_message(
                    embed=BotEmbed.error("No Report Channel", "The staff hasn't configured a report channel. Ask an admin to use `/reportchannel`."),
                    ephemeral=False
                )
                return

            channel = interaction.guild.get_channel(channel_id)
            if channel is None:
                await interaction.response.send_message(
                    embed=BotEmbed.error("Channel Not Found", "The configured report channel no longer exists."),
                    ephemeral=False
                )
                return

            # 2. Build the report embed
            embed = discord.Embed(
                title="🚩 New Message Report",
                color=discord.Color.orange(),
                timestamp=interaction.created_at
            )
            embed.add_field(name="Reported by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reported user", value=self.message.author.mention, inline=True)
            embed.add_field(name="Channel", value=self.message.channel.mention, inline=True)
            embed.add_field(name="Reason", value=self.reason.value, inline=False)

            # Include message content (truncate if needed)
            content = self.message.content or "*No text content*"
            if len(content) > 1024:
                content = content[:1020] + "..."
            embed.add_field(name="Message Content", value=content, inline=False)

            # Add attachment URLs if any
            if self.message.attachments:
                urls = "\n".join([a.url for a in self.message.attachments])
                if len(urls) > 1024:
                    urls = urls[:1020] + "..."
                embed.add_field(name="Attachments", value=urls, inline=False)

            embed.set_footer(text=f"Message ID: {self.message.id} • Click to jump")
            jump_link = f"https://discord.com/channels/{interaction.guild_id}/{self.message.channel.id}/{self.message.id}"
            embed.description = f"[Jump to message]({jump_link})"

            # 3. Send to staff channel
            await channel.send(embed=embed)

            # 4. Confirm to the reporter
            await interaction.response.send_message(
                embed=BotEmbed.success("Reported", "Your report has been submitted to the staff team."),
                ephemeral=False
            )

        except Exception as e:
            print(f"Error in report modal: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    embed=BotEmbed.error("Unexpected Error", "Something went wrong while submitting your report. Please try again later."),
                    ephemeral=False
                )
            except:
                pass

    @staticmethod
    async def get_report_channel(guild_id: int) -> int | None:
        """Return the report channel ID for a guild, or None."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT report_channel_id FROM report_settings WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            if row and row["report_channel_id"]:
                return row["report_channel_id"]
            return None


# -------------------------------------------------------------------
#  1) Context menu: "Report Message" (right‑click a message)
# -------------------------------------------------------------------
@app_commands.context_menu(name="Report Message")
async def report_message_context(interaction: discord.Interaction, message: discord.Message):
    # Prevent reporting your own messages
    if message.author == interaction.user:
        await interaction.response.send_message(
            embed=BotEmbed.error("Cannot Report", "You cannot report your own message."),
            ephemeral=False
        )
        return

    modal = ReportModal(message)
    await interaction.response.prompt_modal(modal)


# -------------------------------------------------------------------
#  2) Slash command: /report (report by message ID)
# -------------------------------------------------------------------
@app_commands.command(name="report", description="Report a message by its ID")
@app_commands.describe(message_id="The ID of the message you want to report", reason="Reason for reporting (optional)")
async def report_slash(interaction: discord.Interaction, message_id: str, reason: str = None):
    try:
        msg_id = int(message_id)
    except ValueError:
        await interaction.response.send_message(
            embed=BotEmbed.error("Invalid ID", "Please provide a valid numeric message ID."),
            ephemeral=False
        )
        return

    # Try to fetch the message (must be in the same guild)
    try:
        message = await interaction.channel.fetch_message(msg_id)
    except discord.NotFound:
        await interaction.response.send_message(
            embed=BotEmbed.error("Message Not Found", "I couldn't find that message. Make sure the ID is correct and it's in this channel."),
            ephemeral=False
        )
        return
    except discord.Forbidden:
        await interaction.response.send_message(
            embed=BotEmbed.error("No Permission", "I don't have permission to read that message."),
            ephemeral=False
        )
        return

    # Prevent reporting own messages
    if message.author == interaction.user:
        await interaction.response.send_message(
            embed=BotEmbed.error("Cannot Report", "You cannot report your own message."),
            ephemeral=False
        )
        return

    # If a reason was provided, we can directly send the report without modal
    if reason:
        channel_id = await ReportModal.get_report_channel(interaction.guild_id)
        if channel_id is None:
            await interaction.response.send_message(
                embed=BotEmbed.error("No Report Channel", "Staff haven't configured a report channel yet."),
                ephemeral=False
            )
            return

        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            await interaction.response.send_message(
                embed=BotEmbed.error("Channel Not Found", "The configured report channel no longer exists."),
                ephemeral=False
            )
            return

        embed = discord.Embed(
            title="🚩 New Message Report",
            color=discord.Color.orange(),
            timestamp=interaction.created_at
        )
        embed.add_field(name="Reported by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reported user", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        content = message.content or "*No text content*"
        if len(content) > 1024:
            content = content[:1020] + "..."
        embed.add_field(name="Message Content", value=content, inline=False)
        if message.attachments:
            urls = "\n".join([a.url for a in message.attachments])
            if len(urls) > 1024:
                urls = urls[:1020] + "..."
            embed.add_field(name="Attachments", value=urls, inline=False)
        jump_link = f"https://discord.com/channels/{interaction.guild_id}/{message.channel.id}/{message.id}"
        embed.description = f"[Jump to message]({jump_link})"
        embed.set_footer(text=f"Message ID: {message.id}")

        await channel.send(embed=embed)
        await interaction.response.send_message(
            embed=BotEmbed.success("Reported", "Your report has been submitted to the staff team."),
            ephemeral=False
        )
    else:
        modal = ReportModal(message)
        await interaction.response.prompt_modal(modal)


# -------------------------------------------------------------------
#  Cog: provides the /reportchannel command for admins
# -------------------------------------------------------------------
class Report(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reportchannel", description="Set the channel where reports are sent")
    @app_commands.describe(channel="The channel that will receive user reports")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reportchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS report_settings (
                    guild_id INTEGER PRIMARY KEY,
                    report_channel_id INTEGER NOT NULL
                )
            """)
            await db.execute(
                "INSERT OR REPLACE INTO report_settings (guild_id, report_channel_id) VALUES (?, ?)",
                (interaction.guild_id, channel.id)
            )
            await db.commit()
        await interaction.response.send_message(
            embed=BotEmbed.success("Report Channel Set", f"Reports will now be sent to {channel.mention}."),
            ephemeral=False
        )


# -------------------------------------------------------------------
#  Setup: create tables, add Cog, register context menu & slash command
# -------------------------------------------------------------------
async def setup(bot):
    # Ensure the report_settings table exists
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS report_settings (
                guild_id INTEGER PRIMARY KEY,
                report_channel_id INTEGER NOT NULL
            )
        """)
        await db.commit()

    # Add the Cog (this registers the /reportchannel command)
    await bot.add_cog(Report(bot))

    # Manually add the context menu and the /report command to the tree
    bot.tree.add_command(report_message_context)
    bot.tree.add_command(report_slash)