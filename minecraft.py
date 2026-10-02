import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import os
from formatter import BotEmbed
from mcstatus import JavaServer, BedrockServer

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")


class MinecraftStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_panels.start()

    def cog_unload(self):
        self.update_panels.cancel()

    # ---------- Core query ----------
    async def query_server(self, address: str, edition: str):
        try:
            if edition == "bedrock":
                target = address if ":" in address else f"{address}:19132"
                server = BedrockServer.lookup(target)
                status = await server.async_status()

                embed = discord.Embed(
                    title=f"🟢 {address} — Online",
                    color=0x57F287,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Edition", value="Bedrock", inline=True)
                embed.add_field(name="Players", value=f"{status.players.online}/{status.players.max}", inline=True)
                embed.add_field(name="Version", value=status.version.name, inline=True)
                if getattr(status, "gamemode", None):
                    embed.add_field(name="Gamemode", value=status.gamemode, inline=True)
                if getattr(status, "map", None):
                    embed.add_field(name="Map", value=status.map, inline=True)
                motd = getattr(status, "motd", None)
                if motd:
                    motd_text = getattr(motd, "raw", None) or str(motd)
                    embed.add_field(name="MOTD", value=f"```{motd_text[:1000]}```", inline=False)
                return embed

            else:
                server = JavaServer.lookup(address)
                status = await server.async_status()

                embed = discord.Embed(
                    title=f"🟢 {address} — Online",
                    color=0x57F287,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Edition", value="Java", inline=True)
                embed.add_field(name="Players", value=f"{status.players.online}/{status.players.max}", inline=True)
                embed.add_field(name="Version", value=status.version.name, inline=True)
                embed.add_field(name="Latency", value=f"{round(status.latency)}ms", inline=True)

                motd_text = ""
                if getattr(status, "motd", None):
                    motd_text = getattr(status.motd, "raw", None) or str(status.motd)
                if motd_text:
                    embed.add_field(name="MOTD", value=f"```{motd_text[:1000]}```", inline=False)

                if status.players.sample:
                    names = ", ".join(p.name for p in status.players.sample[:20])
                    embed.add_field(name="Players Online", value=names[:1000], inline=False)
                return embed

        except Exception as e:
            return BotEmbed.error(
                "Server Offline / Unreachable",
                f"Could not reach `{address}` ({edition}).\n```{str(e)[:500]}```"
            )

    # ---------- /mcstatus ----------
    @app_commands.command(name="mcstatus", description="Check a Minecraft server's live status (one-time)")
    @app_commands.describe(
        address="Server address (e.g., play.example.com or play.example.com:25565)",
        edition="Java or Bedrock (default: Java)"
    )
    @app_commands.choices(edition=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock"),
    ])
    async def mcstatus(
        self,
        interaction: discord.Interaction,
        address: str,
        edition: str = "java"
    ):
        await interaction.response.defer()
        embed = await self.query_server(address, edition)
        await interaction.followup.send(embed=embed)

    # ---------- /mclive ----------
    @app_commands.command(name="mclive", description="Start or stop a live Minecraft status panel in this channel")
    @app_commands.describe(
        address="Server address (omit this to stop the panel)",
        edition="Java or Bedrock (default: Java)"
    )
    @app_commands.choices(edition=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock"),
    ])
    async def mclive(
        self,
        interaction: discord.Interaction,
        address: str = None,
        edition: str = "java"
    ):
        # ---- Stop mode ----
        if address is None:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT message_id FROM mc_live_panels WHERE channel_id = ?",
                    (interaction.channel_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return await interaction.response.send_message(
                        embed=BotEmbed.info("No Panel", "There is no live panel in this channel."),
                        ephemeral=True
                    )
                await db.execute("DELETE FROM mc_live_panels WHERE channel_id = ?", (interaction.channel_id,))
                await db.commit()

            # Try to mark the old panel as stopped
            try:
                msg = await interaction.channel.fetch_message(row["message_id"])
                stopped = discord.Embed(
                    title="🛑 Live panel stopped",
                    description="This panel is no longer being updated.",
                    color=0x888888
                )
                await msg.edit(embed=stopped)
            except Exception:
                pass

            return await interaction.response.send_message(
                embed=BotEmbed.success("Stopped", "The live status panel has been stopped."),
                ephemeral=True
            )

        # ---- Start mode ----
        await interaction.response.defer()

        # Check for existing panel in this channel
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM mc_live_panels WHERE channel_id = ?",
                (interaction.channel_id,)
            )
            if await cursor.fetchone():
                return await interaction.followup.send(
                    embed=BotEmbed.warning(
                        "Panel Already Exists",
                        "This channel already has a live panel. Stop it first with `/mclive` (no address)."
                    )
                )

        embed = await self.query_server(address, edition)
        msg = await interaction.followup.send(embed=embed)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mc_live_panels "
                "(channel_id, guild_id, message_id, address, edition) VALUES (?, ?, ?, ?, ?)",
                (interaction.channel_id, interaction.guild_id, msg.id, address, edition)
            )
            await db.commit()

    # ---------- Background update loop ----------
    @tasks.loop(seconds=60)
    async def update_panels(self):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM mc_live_panels")
            panels = await cursor.fetchall()

        to_delete = []
        for panel in panels:
            channel = self.bot.get_channel(panel["channel_id"])
            if not channel:
                to_delete.append(panel["channel_id"])
                continue

            try:
                msg = await channel.fetch_message(panel["message_id"])
            except (discord.NotFound, discord.Forbidden):
                to_delete.append(panel["channel_id"])
                continue
            except Exception:
                continue

            embed = await self.query_server(panel["address"], panel["edition"])
            try:
                await msg.edit(embed=embed)
            except Exception:
                pass

        if to_delete:
            async with aiosqlite.connect(DB_PATH) as db:
                for cid in to_delete:
                    await db.execute("DELETE FROM mc_live_panels WHERE channel_id = ?", (cid,))
                await db.commit()

    @update_panels.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mc_live_panels (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                address TEXT NOT NULL,
                edition TEXT DEFAULT 'java'
            )
        """)
        await db.commit()
    await bot.add_cog(MinecraftStatus(bot))