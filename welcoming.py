import os
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")


class Welcoming(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _ensure_table(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcoming_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_channel_id INTEGER DEFAULT 0,
                    welcome_message TEXT DEFAULT 'Welcome {user}!',
                    farewell_channel_id INTEGER DEFAULT 0,
                    auto_role_id INTEGER DEFAULT 0
                )
            """)
            await db.commit()

    async def get_settings(self, guild_id: int) -> dict:
        await self._ensure_table()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM welcoming_settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "welcome_channel_id": row["welcome_channel_id"],
                    "welcome_message": row["welcome_message"],
                    "farewell_channel_id": row["farewell_channel_id"],
                    "auto_role_id": row["auto_role_id"]
                }
            return {
                "welcome_channel_id": 0,
                "welcome_message": "Welcome {user}!",
                "farewell_channel_id": 0,
                "auto_role_id": 0
            }

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await self.get_settings(member.guild.id)
        role_id = settings.get("auto_role_id")
        if role_id:
            role = member.guild.get_role(role_id)
            if role and role.is_assignable():
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        channel_id = settings.get("welcome_channel_id")
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await member.guild.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    channel = None
            if channel:
                msg = settings.get("welcome_message", "Welcome {user}!")
                msg = msg.replace("{user}", member.mention).replace("{server}", member.guild.name)
                try:
                    await channel.send(msg)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        settings = await self.get_settings(member.guild.id)
        channel_id = settings.get("farewell_channel_id")
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await member.guild.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    channel = None
            if channel:
                try:
                    await channel.send(f"👋 {member.mention} has left the server.")
                except (discord.Forbidden, discord.HTTPException):
                    pass

    @app_commands.command(name="welcome", description="Configure welcome settings")
    @app_commands.describe(action="Setting to change", channel="Target channel", message="Welcome message", role="Auto role")
    @app_commands.choices(action=[
        app_commands.Choice(name="channel", value="channel"),
        app_commands.Choice(name="message", value="message"),
        app_commands.Choice(name="role", value="role"),
        app_commands.Choice(name="test", value="test"),
    ])
    @admin_only()
    async def welcome(self, interaction: discord.Interaction, action: str, channel: discord.TextChannel | None = None, message: str | None = None, role: discord.Role | None = None):
        guild_id = interaction.guild_id
        await self._ensure_table()

        if action == "channel":
            if not channel:
                embed = BotEmbed.error("Missing Channel", "Please specify a text channel.")
                return await interaction.response.send_message(embed=embed, ephemeral=False)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO welcoming_settings (guild_id, welcome_channel_id) VALUES (?, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET welcome_channel_id = ?",
                    (guild_id, channel.id, channel.id)
                )
                await db.commit()
            embed = BotEmbed.success("Welcome Channel", f"Set to {channel.mention}.")
        elif action == "message":
            if not message:
                embed = BotEmbed.error("Missing Message", "Provide a welcome message.")
                return await interaction.response.send_message(embed=embed, ephemeral=False)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO welcoming_settings (guild_id, welcome_message) VALUES (?, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET welcome_message = ?",
                    (guild_id, message, message)
                )
                await db.commit()
            embed = BotEmbed.success("Welcome Message", "Message updated.")
        elif action == "role":
            if not role:
                embed = BotEmbed.error("Missing Role", "Mention a role to auto-assign.")
                return await interaction.response.send_message(embed=embed, ephemeral=False)
            if role >= interaction.guild.me.top_role:
                embed = BotEmbed.error("Role Too High", "I cannot assign a role higher than my own.")
                return await interaction.response.send_message(embed=embed, ephemeral=False)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO welcoming_settings (guild_id, auto_role_id) VALUES (?, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET auto_role_id = ?",
                    (guild_id, role.id, role.id)
                )
                await db.commit()
            embed = BotEmbed.success("Auto Role", f"{role.mention} will be assigned to new members.")
        elif action == "test":
            settings = await self.get_settings(guild_id)
            channel_id = settings.get("welcome_channel_id")
            if not channel_id:
                embed = BotEmbed.error("Not Set", "Welcome channel is not configured.")
                return await interaction.response.send_message(embed=embed, ephemeral=False)
            target = interaction.guild.get_channel(channel_id)
            if target:
                msg = settings.get("welcome_message", "Welcome {user}!")
                msg = msg.replace("{user}", interaction.user.mention).replace("{server}", interaction.guild.name)
                await target.send(msg)
                embed = BotEmbed.success("Test Sent", "Welcome message test sent.")
            else:
                embed = BotEmbed.error("Channel Not Found", "The saved channel no longer exists.")
        else:
            embed = BotEmbed.error("Invalid Action", "Choose a valid welcome configuration action.")

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="farewell", description="Set farewell channel")
    @app_commands.describe(channel="Channel for leave messages")
    @admin_only()
    async def farewell(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._ensure_table()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO welcoming_settings (guild_id, farewell_channel_id) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET farewell_channel_id = ?",
                (interaction.guild_id, channel.id, channel.id)
            )
            await db.commit()
        embed = BotEmbed.success("Farewell Channel", f"Set to {channel.mention}.")
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot):
    cog = Welcoming(bot)
    await cog._ensure_table()
    await bot.add_cog(cog)
