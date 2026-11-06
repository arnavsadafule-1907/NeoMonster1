from datetime import timedelta
import importlib
import os
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only, is_extra_owner
from formatter import BotEmbed


def get_emoji(name: str):
    try:
        module = importlib.import_module("utils.emoji_manager")
        return module.get_emoji(name)
    except (ImportError, AttributeError):
        return ""

def get_db_path() -> str:
    return os.getenv("DATABASE_PATH", "./data/security.db")


class MassMention(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_settings(self, guild_id: int) -> dict:
        async with aiosqlite.connect(get_db_path()) as db:
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
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.id == self.bot.user.id:
            return
        if message.author.id == message.guild.owner_id or message.author.id in self.bot.owner_ids:
            return
        if await is_extra_owner(message.guild.id, message.author.id):
            return

        if message.author.bot:
            try:
                from botwhitelist import is_bot_whitelisted
                if await is_bot_whitelisted(message.guild.id, message.author.id):
                    return
            except ImportError:
                pass

        settings = await self.get_settings(message.guild.id)
        if not settings["enabled"]:
            return

        mentions = getattr(message, "mentions", [])
        role_mentions = getattr(message, "role_mentions", [])
        mention_count = len(mentions) + len(role_mentions)
        if getattr(message, "mention_everyone", False):
            mention_count += 1

        if mention_count >= settings["threshold"]:
            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

            try:
                punishment = settings.get("punishment", "mute")
                if isinstance(message.author, discord.Member):
                    if punishment == "mute":
                        await message.author.timeout(
                            discord.utils.utcnow() + timedelta(hours=1),
                            reason=f"Mass mention ({mention_count} mentions)"
                        )
                    elif punishment == "kick":
                        await message.author.kick(reason="Mass mention spam")
                    elif punishment == "ban":
                        await message.author.ban(reason="Mass mention spam", delete_message_days=1)
            except (discord.Forbidden, discord.HTTPException):
                pass

            async with aiosqlite.connect(get_db_path()) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT log_channel_id FROM guild_settings WHERE guild_id = ?", (message.guild.id,))
                row = await cursor.fetchone()
                if row and row["log_channel_id"]:
                    log_channel = message.guild.get_channel(row["log_channel_id"])
                    if log_channel:
                        alert_icon = get_emoji("siren")
                        title = f"{alert_icon} Mass Mention Detected" if alert_icon else "Mass Mention Detected"
                        embed = discord.Embed(
                            title=title,
                            description=f"**User:** {message.author.mention} (`{message.author.id}`)\n"
                                        f"**Mentions:** `{mention_count}` (Threshold: `{settings['threshold']}`)\n"
                                        f"**Punishment:** `{settings['punishment']}`\n"
                                        f"**Channel:** {message.channel.mention}",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                        try:
                            await log_channel.send(embed=embed)
                        except (discord.Forbidden, discord.HTTPException):
                            pass

    mention_group = app_commands.Group(name="massmention", description="Configure mass mention protection")

    @mention_group.command(name="enable", description="Enable mass mention protection")
    @admin_only()
    async def enable(self, interaction: discord.Interaction):
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                "INSERT INTO massmention_settings (guild_id, enabled) VALUES (?, 1) "
                "ON CONFLICT(guild_id) DO UPDATE SET enabled = 1",
                (interaction.guild_id,)
            )
            await db.commit()
        embed = BotEmbed.success("Mass Mention Protection", "Protection has been **enabled**.")
        await interaction.response.send_message(embed=embed)

    @mention_group.command(name="disable", description="Disable mass mention protection")
    @admin_only()
    async def disable(self, interaction: discord.Interaction):
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                "INSERT INTO massmention_settings (guild_id, enabled) VALUES (?, 0) "
                "ON CONFLICT(guild_id) DO UPDATE SET enabled = 0",
                (interaction.guild_id,)
            )
            await db.commit()
        embed = BotEmbed.warning("Mass Mention Protection", "Protection has been **disabled**.")
        await interaction.response.send_message(embed=embed)

    @mention_group.command(name="threshold", description="Set the maximum allowed mentions per message")
    @app_commands.describe(amount="Number of mentions to trigger punishment (e.g. 5)")
    @admin_only()
    async def set_threshold(self, interaction: discord.Interaction, amount: int):
        if amount < 2:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Invalid Threshold", "Threshold must be at least 2."),
                ephemeral=True
            )
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                "INSERT INTO massmention_settings (guild_id, threshold) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET threshold = ?",
                (interaction.guild_id, amount, amount)
            )
            await db.commit()
        embed = BotEmbed.success("Threshold Updated", f"Threshold set to **{amount}** mentions.")
        await interaction.response.send_message(embed=embed)

    @mention_group.command(name="punishment", description="Set the punishment for mass mentions")
    @app_commands.describe(action="The punishment to apply")
    @app_commands.choices(action=[
        app_commands.Choice(name="Mute (1 hour)", value="mute"),
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Ban", value="ban"),
    ])
    @admin_only()
    async def set_punishment(self, interaction: discord.Interaction, action: str):
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                "INSERT INTO massmention_settings (guild_id, punishment) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET punishment = ?",
                (interaction.guild_id, action, action)
            )
            await db.commit()
        embed = BotEmbed.success("Punishment Updated", f"Punishment set to **{action}**.")
        await interaction.response.send_message(embed=embed)

    @mention_group.command(name="status", description="View current mass mention protection settings")
    async def status(self, interaction: discord.Interaction):
        settings = await self.get_settings(interaction.guild_id)
        embed = BotEmbed.info(
            "Mass Mention Settings",
            f"**Status:** {'Enabled ' + get_emoji('tick') if settings['enabled'] else 'Disabled ' + get_emoji('cross')}\n"
            f"**Threshold:** `{settings['threshold']}` mentions\n"
            f"**Punishment:** `{settings['punishment']}`"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    async with aiosqlite.connect(get_db_path()) as db:
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
