import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

class MassMention(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_settings(self, guild_id: int) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM massmention_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "enabled": bool(row["enabled"]),
                    "threshold": row["threshold"],
                    "punishment": row["punishment"]
                }
            return {"enabled": True, "threshold": 10, "punishment": "mute"}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        settings = await self.get_settings(message.guild.id)
        if not settings["enabled"]:
            return

        # Count mentions (users + roles + @everyone/@here)
        mention_count = len(message.mentions) + len(message.role_mentions)
        if message.mention_everyone:
            mention_count += 1

        if mention_count >= settings["threshold"]:
            # Delete the message
            try:
                await message.delete()
            except:
                pass

            # Punish the user
            try:
                if settings["punishment"] == "mute":
                    await message.author.timeout(
                        discord.utils.utcnow() + discord.timedelta(hours=1),
                        reason=f"Mass mention ({mention_count} mentions)"
                    )
                elif settings["punishment"] == "kick":
                    await message.author.kick(reason="Mass mention spam")
                elif settings["punishment"] == "ban":
                    await message.author.ban(reason="Mass mention spam", delete_message_days=1)
            except discord.Forbidden:
                pass

            # Alert staff via log channel
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT log_channel_id FROM guild_settings WHERE guild_id = ?", (message.guild.id,))
                row = await cursor.fetchone()
                if row and row["log_channel_id"]:
                    log_channel = message.guild.get_channel(row["log_channel_id"])
                    if log_channel:
                        embed = discord.Embed(
                            title="🚨 Mass Mention Detected",
                            description=f"{message.author.mention} mentioned **{mention_count}** users/roles.",
                            color=discord.Color.red()
                        )
                        embed.add_field(name="Channel", value=message.channel.mention)
                        embed.add_field(name="Punishment", value=settings["punishment"])
                        embed.set_footer(text=f"User ID: {message.author.id}")
                        await log_channel.send(embed=embed)

    @app_commands.command(name="massmention", description="Configure mass mention protection")
    @app_commands.describe(action="Setting to change", value="Value (for threshold)")
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
        app_commands.Choice(name="threshold", value="threshold"),
        app_commands.Choice(name="punishment", value="punishment"),
    ])
    @app_commands.choices(punishment=[
        app_commands.Choice(name="mute", value="mute"),
        app_commands.Choice(name="kick", value="kick"),
        app_commands.Choice(name="ban", value="ban"),
    ])
    @admin_only()
    async def massmention(self, interaction: discord.Interaction, action: str, value: str = None, punishment: str = None):
        guild_id = interaction.guild_id
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO massmention_settings (guild_id) VALUES (?)", (guild_id,))
            await db.commit()

        if action == "enable":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE massmention_settings SET enabled = 1 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.success("Mass Mention Protection", "Enabled.")
        elif action == "disable":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE massmention_settings SET enabled = 0 WHERE guild_id = ?", (guild_id,))
                await db.commit()
            embed = BotEmbed.success("Mass Mention Protection", "Disabled.")
        elif action == "threshold":
            if not value or not value.isdigit() or int(value) < 2:
                embed = BotEmbed.error("Invalid", "Threshold must be at least 2.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE massmention_settings SET threshold = ? WHERE guild_id = ?", (int(value), guild_id))
                await db.commit()
            embed = BotEmbed.success("Threshold Updated", f"Will trigger at `{value}` mentions.")
        elif action == "punishment":
            if not punishment:
                embed = BotEmbed.error("Invalid", "Choose a punishment: mute, kick, or ban.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE massmention_settings SET punishment = ? WHERE guild_id = ?", (punishment, guild_id))
                await db.commit()
            embed = BotEmbed.success("Punishment Updated", f"Offenders will be `{punishment}`ed.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS massmention_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                threshold INTEGER DEFAULT 10,
                punishment TEXT DEFAULT 'mute'
            )
        """)
        await db.commit()
    await bot.add_cog(MassMention(bot))