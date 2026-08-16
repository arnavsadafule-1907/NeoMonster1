import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import os
from datetime import datetime, timezone

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# ====================================================================
#  CHANNEL IDs – the bot will monitor these for knowledge updates
# ====================================================================
KNOWLEDGE_CHANNELS = [
    1534097938022793266,  # announce
    1537491982044373013,  # poll
    1537491842591883426,  # event
    1534119515565326346,  # rules
    1537491924045529110,  # server updates
    1537491731593822290,  # server concept
    1537491780776361996,  # custom recipes
    1525873414080823556,  # server kit
    1536210596222083082,  # server status
    1537796894867066980,  # ranked smp
    1537797210819792927,  # strength smp
    1537475289834065941,  # get whitelist
    1537846246629449809,  # team register
    1534209707047129248,  # booster perks
    1530079728956866661,  # punishment
    1525874371695083671,  # tickets
    1537799580190515291,  # strength abilities
    1537799391266476062,  # texture pack
]

class KnowledgeUpdater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.knowledge_channels = KNOWLEDGE_CHANNELS.copy()  # store IDs
        self.update_loop.start()

    def cog_unload(self):
        self.update_loop.cancel()

    @tasks.loop(minutes=5)
    async def update_loop(self):
        await self.refresh_knowledge()

    @update_loop.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

    async def refresh_knowledge(self):
        """Fetch messages from all configured channels and update the database."""
        for channel_id in self.knowledge_channels:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                # If the channel isn't found (e.g., bot not in that guild), skip
                continue

            async with aiosqlite.connect(DB_PATH) as db:
                # Clear old entries for this channel
                await db.execute("DELETE FROM knowledge_entries WHERE channel_id = ?", (channel_id,))

                # Fetch last 150 messages (or adjust as needed)
                async for msg in channel.history(limit=150):
                    # Skip messages from bots to avoid loops
                    if msg.author.bot:
                        continue

                    # Parse: if message starts with "!kb: SectionName", treat as a section
                    if msg.content.startswith("!kb:"):
                        lines = msg.content[4:].split("\n")
                        section = lines[0].strip() if lines else "general"
                        content = "\n".join(lines[1:]) if len(lines) > 1 else ""
                        if content:
                            await db.execute(
                                "INSERT INTO knowledge_entries (channel_id, section, content, last_updated) VALUES (?, ?, ?, ?)",
                                (channel_id, section, content, datetime.now(timezone.utc).isoformat())
                            )
                    else:
                        # Store the entire message as a generic entry
                        await db.execute(
                            "INSERT INTO knowledge_entries (channel_id, section, content, last_updated) VALUES (?, ?, ?, ?)",
                            (channel_id, "general", msg.content, datetime.now(timezone.utc).isoformat())
                        )
                await db.commit()

    @app_commands.command(name="refreshknowledge", description="Manually refresh the knowledge base from all channels")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def refresh_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.refresh_knowledge()
        embed = discord.Embed(title="✅ Knowledge Refreshed", description="All channels have been synced.", color=0x00FF00)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="addknowledgechannel", description="Add an extra channel to monitor (for future use)")
    @app_commands.describe(channel="The text channel to monitor")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if channel.id in self.knowledge_channels:
            embed = discord.Embed(title="⚠️ Already Monitored", color=0xFFA500)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        self.knowledge_channels.append(channel.id)
        # Also store in database for persistence across restarts
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO knowledge_channels (guild_id, channel_id) VALUES (?, ?)", (interaction.guild_id, channel.id))
            await db.commit()
        embed = discord.Embed(title="✅ Channel Added", description=f"Now monitoring {channel.mention}", color=0x00FF00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="removeknowledgechannel", description="Stop monitoring a channel")
    @app_commands.describe(channel="The channel to remove")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if channel.id not in self.knowledge_channels:
            embed = discord.Embed(title="⚠️ Not Monitored", color=0xFFA500)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        self.knowledge_channels.remove(channel.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM knowledge_channels WHERE guild_id = ? AND channel_id = ?", (interaction.guild_id, channel.id))
            await db.commit()
        embed = discord.Embed(title="✅ Channel Removed", color=0x00FF00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    # Ensure the tables exist
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                section TEXT,
                content TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_channels (
                guild_id INTEGER,
                channel_id INTEGER PRIMARY KEY
            )
        """)
        await db.commit()

    cog = KnowledgeUpdater(bot)

    # Load any extra channels saved from previous /addknowledgechannel commands
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT channel_id FROM knowledge_channels")
        rows = await cursor.fetchall()
        for row in rows:
            if row[0] not in cog.knowledge_channels:
                cog.knowledge_channels.append(row[0])

    await bot.add_cog(cog)