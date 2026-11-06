import os
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")


class Ignore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cache: dict[int, dict[str, set[int]]] = {}

    async def _ensure_table(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ignored_entities (
                    guild_id INTEGER NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, entity_type, entity_id)
                )
            """)
            await db.commit()

    async def is_ignored(self, guild_id: int | None, user_id: int, channel_id: int | None) -> bool:
        if not guild_id:
            return False
        if guild_id not in self._cache:
            await self._load_guild_cache(guild_id)
        guild_cache = self._cache.get(guild_id, {"user": set(), "channel": set()})
        if user_id in guild_cache["user"]:
            return True
        if channel_id and channel_id in guild_cache["channel"]:
            return True
        return False

    async def _load_guild_cache(self, guild_id: int):
        await self._ensure_table()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT entity_type, entity_id FROM ignored_entities WHERE guild_id = ?", (guild_id,))
            rows = await cursor.fetchall()
        user_set: set[int] = set()
        channel_set: set[int] = set()
        for r in rows:
            if r["entity_type"] == "user":
                user_set.add(r["entity_id"])
            elif r["entity_type"] == "channel":
                channel_set.add(r["entity_id"])
        self._cache[guild_id] = {"user": user_set, "channel": channel_set}

    @app_commands.command(name="ignore", description="Make the bot ignore a user or channel in this server")
    @app_commands.describe(target_type="User or channel", user="User to ignore", channel="Channel to ignore")
    @app_commands.choices(target_type=[
        app_commands.Choice(name="user", value="user"),
        app_commands.Choice(name="channel", value="channel"),
    ])
    @admin_only()
    async def ignore(self, interaction: discord.Interaction, target_type: str, user: discord.User | None = None, channel: discord.TextChannel | None = None):
        await self._ensure_table()
        guild_id = interaction.guild_id

        if target_type == "user" and user:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR IGNORE INTO ignored_entities (guild_id, entity_type, entity_id) VALUES (?, 'user', ?)", (guild_id, user.id))
                await db.commit()
            self._cache.setdefault(guild_id, {"user": set(), "channel": set()})["user"].add(user.id)
            embed = BotEmbed.success("Ignored User", f"Now ignoring {user.mention} in this server.")
        elif target_type == "channel" and channel:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR IGNORE INTO ignored_entities (guild_id, entity_type, entity_id) VALUES (?, 'channel', ?)", (guild_id, channel.id))
                await db.commit()
            self._cache.setdefault(guild_id, {"user": set(), "channel": set()})["channel"].add(channel.id)
            embed = BotEmbed.success("Ignored Channel", f"Now ignoring {channel.mention} in this server.")
        else:
            embed = BotEmbed.error("Invalid Target", "Provide a user or channel.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unignore", description="Remove ignore status for a user or channel")
    @app_commands.describe(target_type="User or channel", user="User to unignore", channel="Channel to unignore")
    @app_commands.choices(target_type=[
        app_commands.Choice(name="user", value="user"),
        app_commands.Choice(name="channel", value="channel"),
    ])
    @admin_only()
    async def unignore(self, interaction: discord.Interaction, target_type: str, user: discord.User | None = None, channel: discord.TextChannel | None = None):
        await self._ensure_table()
        guild_id = interaction.guild_id

        if target_type == "user" and user:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM ignored_entities WHERE guild_id = ? AND entity_type = 'user' AND entity_id = ?", (guild_id, user.id))
                await db.commit()
            if guild_id in self._cache:
                self._cache[guild_id]["user"].discard(user.id)
            embed = BotEmbed.success("Unignored User", f"No longer ignoring {user.mention}.")
        elif target_type == "channel" and channel:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM ignored_entities WHERE guild_id = ? AND entity_type = 'channel' AND entity_id = ?", (guild_id, channel.id))
                await db.commit()
            if guild_id in self._cache:
                self._cache[guild_id]["channel"].discard(channel.id)
            embed = BotEmbed.success("Unignored Channel", f"No longer ignoring {channel.mention}.")
        else:
            embed = BotEmbed.error("Invalid Target", "Provide a user or channel.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    cog = Ignore(bot)
    await cog._ensure_table()
    await bot.add_cog(cog)
