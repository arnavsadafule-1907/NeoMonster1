import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
from formatter import BotEmbed
from checks import admin_only
from mcstatus import JavaServer, BedrockServer

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")


class MinecraftStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- DB helpers ----------
    async def get_default(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM mc_servers WHERE guild_id = ?", (guild_id,)
            )
            return await cursor.fetchone()

    async def set_default(self, guild_id: int, address: str, edition: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mc_servers (guild_id, address, edition) VALUES (?, ?, ?)",
                (guild_id, address, edition)
            )
            await db.commit()

    async def remove_default(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM mc_servers WHERE guild_id = ?", (guild_id,))
            await db.commit()

    # ---------- Core query ----------
    async def query_server(self, address: str, edition: str):
        try:
            if edition == "bedrock":
                # Bedrock default port is 19132
                target = address if ":" in address else f"{address}:19132"
                server = BedrockServer.lookup(target)
                status = await server.async_status()

                embed = discord.Embed(
                    title=f"🟢 {address} — Online",
                    color=0x57F287,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Edition", value="Bedrock", inline=True)
                embed.add_field(
                    name="Players",
                    value=f"{status.players.online}/{status.players.max}",
                    inline=True
                )
                embed.add_field(name="Version", value=status.version.name, inline=True)
                if getattr(status, "gamemode", None):
                    embed.add_field(name="Gamemode", value=status.gamemode, inline=True)
                if getattr(status, "map", None):
                    embed.add_field(name="Map", value=status.map, inline=True)

                motd = getattr(status, "motd", None)
                if motd:
                    motd_text = getattr(motd, "raw", None) or str(motd)
                    embed.add_field(
                        name="MOTD",
                        value=f"```{motd_text[:1000]}```",
                        inline=False
                    )
                return embed

            else:  # Java
                server = JavaServer.lookup(address)
                status = await server.async_status()

                embed = discord.Embed(
                    title=f"🟢 {address} — Online",
                    color=0x57F287,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Edition", value="Java", inline=True)
                embed.add_field(
                    name="Players",
                    value=f"{status.players.online}/{status.players.max}",
                    inline=True
                )
                embed.add_field(name="Version", value=status.version.name, inline=True)
                embed.add_field(name="Latency", value=f"{round(status.latency)}ms", inline=True)

                motd_text = ""
                if getattr(status, "motd", None):
                    motd_text = getattr(status.motd, "raw", None) or str(status.motd)
                if motd_text:
                    embed.add_field(
                        name="MOTD",
                        value=f"```{motd_text[:1000]}```",
                        inline=False
                    )

                # Sample of online players (Java only)
                if status.players.sample:
                    names = ", ".join(p.name for p in status.players.sample[:20])
                    embed.add_field(name="Players Online", value=names[:1000], inline=False)

                return embed

        except Exception as e:
            return BotEmbed.error(
                "Server Offline / Unreachable",
                f"Could not reach `{address}` ({edition}).\n```{str(e)[:500]}```"
            )

    # ---------- Shared handler ----------
    async def _handle(self, interaction: discord.Interaction, address: str, edition: str):
        await interaction.response.defer()

        if not address:
            row = await self.get_default(interaction.guild_id)
            if not row:
                return await interaction.followup.send(
                    embed=BotEmbed.error(
                        "No Default Server",
                        "No address provided and no default set.\n"
                        "Use `/setserver <address>` first, or pass an address: `/serverstatus play.example.com`."
                    )
                )
            address = row["address"]
            edition = row["edition"]

        embed = await self.query_server(address, edition)
        await interaction.followup.send(embed=embed)

    # ---------- /serverstatus ----------
    @app_commands.command(name="serverstatus", description="Check a Minecraft server's live status")
    @app_commands.describe(
        address="Server address (e.g., play.example.com or play.example.com:25565)",
        edition="Java or Bedrock (default: Java)"
    )
    @app_commands.choices(edition=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock"),
    ])
    async def serverstatus(
        self,
        interaction: discord.Interaction,
        address: str = None,
        edition: str = "java"
    ):
        await self._handle(interaction, address, edition)

    # ---------- /livestatus (alias) ----------
    @app_commands.command(name="livestatus", description="Alias for /serverstatus")
    @app_commands.describe(
        address="Server address (e.g., play.example.com or play.example.com:25565)",
        edition="Java or Bedrock (default: Java)"
    )
    @app_commands.choices(edition=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock"),
    ])
    async def livestatus(
        self,
        interaction: discord.Interaction,
        address: str = None,
        edition: str = "java"
    ):
        await self._handle(interaction, address, edition)

    # ---------- /setserver (admin only) ----------
    @app_commands.command(name="setserver", description="Set the default Minecraft server for this guild")
    @app_commands.describe(
        address="Server address (e.g., play.example.com or play.example.com:25565)",
        edition="Java or Bedrock"
    )
    @app_commands.choices(edition=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock"),
    ])
    @admin_only()
    async def setserver(
        self,
        interaction: discord.Interaction,
        address: str,
        edition: str = "java"
    ):
        await self.set_default(interaction.guild_id, address, edition)
        await interaction.response.send_message(
            embed=BotEmbed.success(
                "Default Server Set",
                f"`{address}` (**{edition.capitalize()}**) will be used when `/serverstatus` is run without an address."
            )
        )

    # ---------- /removeserver (admin only) ----------
    @app_commands.command(name="removeserver", description="Remove the default Minecraft server for this guild")
    @admin_only()
    async def removeserver(self, interaction: discord.Interaction):
        await self.remove_default(interaction.guild_id)
        await interaction.response.send_message(
            embed=BotEmbed.success("Default Server Removed", "No default server is set anymore.")
        )


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mc_servers (
                guild_id INTEGER PRIMARY KEY,
                address TEXT NOT NULL,
                edition TEXT DEFAULT 'java'
            )
        """)
        await db.commit()
    await bot.add_cog(MinecraftStatus(bot))