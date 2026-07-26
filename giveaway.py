import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import asyncio
import json
import random
from datetime import datetime, timezone
import os
from checks import nuke_only
from formatter import BotEmbed

class GiveawayView(discord.ui.View):
    def __init__(self, db_path, giveaway_id, role_req=None):
        super().__init__(timeout=None)
        self.db_path = db_path
        self.giveaway_id = giveaway_id
        self.role_req = role_req

    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.green, custom_id="join_giveaway")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.role_req and self.role_req != 0:
            role = interaction.guild.get_role(self.role_req)
            if role and role not in interaction.user.roles:
                embed = BotEmbed.error("Role Required", f"You need the {role.mention} role to enter.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT entries, ended FROM giveaways WHERE id = ?", (self.giveaway_id,))
            row = await cursor.fetchone()
            if not row or row["ended"] == 1:
                embed = BotEmbed.error("Ended", "This giveaway has ended.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            entries = json.loads(row["entries"])
            if interaction.user.id in entries:
                entries.remove(interaction.user.id)
                await db.execute("UPDATE giveaways SET entries = ? WHERE id = ?", (json.dumps(entries), self.giveaway_id))
                await db.commit()
                await interaction.response.send_message(embed=BotEmbed.info("Left Giveaway", "You have left the giveaway."), ephemeral=True)
            else:
                entries.append(interaction.user.id)
                await db.execute("UPDATE giveaways SET entries = ? WHERE id = ?", (json.dumps(entries), self.giveaway_id))
                await db.commit()
                await interaction.response.send_message(embed=BotEmbed.success("Entered Giveaway", "You have entered the giveaway!"), ephemeral=True)
            msg = interaction.message
            if msg:
                embed = msg.embeds[0]
                for i, field in enumerate(embed.fields):
                    if field.name == "Entries":
                        embed.set_field_at(i, name="Entries", value=str(len(entries)), inline=True)
                        break
                await msg.edit(embed=embed)

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = os.getenv("DATABASE_PATH", "./data/security.db")
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        await self.bot.wait_until_ready()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM giveaways WHERE ended = 0 AND ends_at <= ?", (now,))
            rows = await cursor.fetchall()
            for gw in rows:
                await self.end_giveaway(db, gw)

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def end_giveaway(self, db, giveaway_row):
        gw_id = giveaway_row["id"]
        channel = self.bot.get_channel(giveaway_row["channel_id"])
        if not channel:
            return
        try:
            message = await channel.fetch_message(giveaway_row["message_id"])
        except discord.NotFound:
            await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", (gw_id,))
            await db.commit()
            return
        entries = json.loads(giveaway_row["entries"])
        winners = []
        if entries:
            num_winners = min(giveaway_row["winners"], len(entries))
            winners = random.sample(entries, num_winners)
        await db.execute("UPDATE giveaways SET ended = 1, entries = ? WHERE id = ?", (json.dumps(winners), gw_id))
        await db.commit()
        embed = message.embeds[0]
        if winners:
            mentions = ", ".join(f"<@{uid}>" for uid in winners)
            embed.add_field(name="Winners", value=mentions, inline=False)
            embed.colour = discord.Color.gold()
        else:
            embed.add_field(name="Winners", value="No valid entries.", inline=False)
            embed.colour = discord.Color.red()
        embed.set_footer(text="Giveaway Ended")
        await message.edit(embed=embed, view=None)
        if winners:
            await channel.send(embed=BotEmbed.success("Giveaway Winners", f"🎉 Congratulations {', '.join(f'<@{uid}>' for uid in winners)}! You won **{giveaway_row['prize']}**!"))
        else:
            await channel.send(embed=BotEmbed.warning("Giveaway Ended", f"No one entered the giveaway for **{giveaway_row['prize']}**..."))

    @app_commands.command(name="gstart", description="Start a giveaway")
    @app_commands.describe(prize="Prize", duration="Duration (10m,2h,1d)", winners="Number of winners", channel="Channel", role="Role required")
    @nuke_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def gstart(self, interaction: discord.Interaction, prize: str, duration: str, winners: int = 1, channel: discord.TextChannel = None, role: discord.Role = None):
        seconds = self.parse_duration(duration)
        if seconds is None:
            embed = BotEmbed.error("Invalid Duration", "Use format like `10m`, `2h`, `1d`.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        target_channel = channel or interaction.channel
        ends_at = datetime.now(timezone.utc).timestamp() + seconds
        ends_at_iso = datetime.fromtimestamp(ends_at, tz=timezone.utc).isoformat()

        embed = discord.Embed(title="🎉 Giveaway!", description=f"**Prize:** {prize}", color=discord.Color.blue(), timestamp=datetime.fromtimestamp(ends_at, tz=timezone.utc))
        embed.add_field(name="Entries", value="0", inline=True)
        embed.add_field(name="Winners", value=str(winners), inline=True)
        if role:
            embed.add_field(name="Role Required", value=role.mention, inline=False)
        embed.set_footer(text="Ends at")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        view = GiveawayView(self.db_path, None, role_req=role.id if role else None)
        await interaction.response.defer(ephemeral=False)
        msg = await target_channel.send(embed=embed, view=view)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winners, role_req, ends_at, ended) VALUES (?,?,?,?,?,?,?,0)",
                (interaction.guild_id, target_channel.id, msg.id, prize, winners, role.id if role else 0, ends_at_iso)
            )
            gw_id = cursor.lastrowid
            await db.commit()
        view.giveaway_id = gw_id
        await msg.edit(view=view)
        await interaction.followup.send(embed=BotEmbed.success("Giveaway Started", f"Giveaway created in {target_channel.mention}."), ephemeral=True)

    @app_commands.command(name="gend", description="End a giveaway early")
    @app_commands.describe(message_id="ID of the giveaway message")
    @nuke_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def gend(self, interaction: discord.Interaction, message_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = 0", (int(message_id), interaction.guild_id))
            gw = await cursor.fetchone()
            if not gw:
                embed = BotEmbed.error("Not Found", "Active giveaway with that message ID not found.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.end_giveaway(db, gw)
            await interaction.response.send_message(embed=BotEmbed.success("Giveaway Ended", "Giveaway ended early."), ephemeral=True)

    @app_commands.command(name="greroll", description="Reroll winners")
    @app_commands.describe(message_id="ID of the giveaway message")
    @nuke_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def greroll(self, interaction: discord.Interaction, message_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = 1", (int(message_id), interaction.guild_id))
            gw = await cursor.fetchone()
            if not gw:
                embed = BotEmbed.error("Not Found", "Ended giveaway not found.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            entries = json.loads(gw["entries"])
            if not entries:
                embed = BotEmbed.error("No Entries", "No entries to reroll.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            num_winners = min(gw["winners"], len(entries))
            new_winners = random.sample(entries, num_winners)
            channel = self.bot.get_channel(gw["channel_id"])
            if channel:
                try:
                    msg = await channel.fetch_message(int(message_id))
                    embed = msg.embeds[0]
                    for i, field in enumerate(embed.fields):
                        if field.name == "Winners":
                            embed.remove_field(i)
                            break
                    mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
                    embed.add_field(name="Winners (Rerolled)", value=mentions, inline=False)
                    await msg.edit(embed=embed)
                except:
                    pass
            await interaction.response.send_message(embed=BotEmbed.success("Rerolled", f"New winners: {', '.join(f'<@{uid}>' for uid in new_winners)}"), ephemeral=False)

    @staticmethod
    def parse_duration(dur_str):
        dur_str = dur_str.lower()
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        if dur_str[-1] in multipliers:
            try:
                value = int(dur_str[:-1])
                return value * multipliers[dur_str[-1]]
            except ValueError:
                return None
        else:
            try:
                return int(dur_str)
            except ValueError:
                return None

async def setup(bot):
    async with aiosqlite.connect(os.getenv("DATABASE_PATH", "./data/security.db")) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                prize TEXT NOT NULL,
                winners INTEGER NOT NULL DEFAULT 1,
                entries TEXT NOT NULL DEFAULT '[]',
                role_req INTEGER NOT NULL DEFAULT 0,
                ends_at TEXT NOT NULL,
                ended INTEGER NOT NULL DEFAULT 0
            )
        ''')
        await db.commit()
    await bot.add_cog(Giveaway(bot))