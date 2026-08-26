import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import aiosqlite
import os
from datetime import datetime, timezone, timedelta
from checks import staff_only, admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
active_polls = {}

# ---------- Embed Builder (clean like the image) ----------
def build_poll_embed(question: str, options: list, end_time: datetime, votes: dict):
    total = sum(votes.values())
    remaining = end_time - datetime.now(timezone.utc)
    if remaining.total_seconds() > 0:
        remaining_str = f"{remaining.seconds // 60}m {remaining.seconds % 60}s"
    else:
        remaining_str = "Closed"

    embed = discord.Embed(
        title=f"📊 {question}",
        color=0x3B82F6,
        timestamp=end_time
    )
    # Each option as a line with count and percentage
    for opt in options:
        count = votes.get(opt, 0)
        percent = (count / total * 100) if total > 0 else 0
        embed.add_field(
            name=opt,
            value=f"`{count}` votes ({percent:.1f}%)",
            inline=False
        )
    embed.set_footer(
        text=f"Total votes: {total}  •  Time left: {remaining_str}  •  Tomorrow at {end_time.strftime('%I:%M %p')}"
    )
    return embed

# ---------- Poll View ----------
class PollView(View):
    def __init__(self, question, options, end_time, guild_id):
        super().__init__(timeout=None)
        self.question = question
        self.options = options
        self.end_time = end_time
        self.votes = {opt: 0 for opt in options}
        self.voter_choice = {}
        self.message = None
        self.guild_id = guild_id

        # One button per option (with the option text as label)
        for opt in options:
            button = Button(label=opt, style=discord.ButtonStyle.primary, custom_id=f"poll_{opt}")
            button.callback = self.make_callback(opt)
            self.add_item(button)

    def make_callback(self, option):
        async def callback(interaction: discord.Interaction):
            user = interaction.user
            if user.id in self.voter_choice:
                old = self.voter_choice[user.id]
                self.votes[old] -= 1
            self.votes[option] += 1
            self.voter_choice[user.id] = option

            embed = build_poll_embed(self.question, self.options, self.end_time, self.votes)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message(f"✅ You voted for **{option}**.", ephemeral=True)
        return callback

    async def close_poll(self):
        for child in self.children:
            child.disabled = True
        embed = build_poll_embed(self.question, self.options, self.end_time, self.votes)
        embed.set_footer(text="⏰ Poll closed • Results finalised")
        if self.message:
            await self.message.edit(embed=embed, view=self)

# ---------- Auto‑close ----------
async def auto_close_poll(poll_id):
    await asyncio.sleep(0.5)
    if poll_id not in active_polls:
        return
    data = active_polls[poll_id]
    now = datetime.now(timezone.utc)
    wait = (data["end_time"] - now).total_seconds()
    if wait > 0:
        await asyncio.sleep(wait)
    view = data["view"]
    view.message = data["message"]
    await view.close_poll()
    active_polls.pop(poll_id, None)

# ---------- Cog ----------
class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(question="The poll question", options="Comma‑separated options (max 10)", duration="Minutes (1-1440)")
    @staff_only()
    async def poll_create(self, interaction: discord.Interaction, question: str, options: str, duration: int):
        if duration < 1 or duration > 1440:
            return await interaction.response.send_message("Duration must be 1‑1440 minutes.", ephemeral=True)

        raw = [opt.strip() for opt in options.split(",") if opt.strip()]
        if len(raw) < 2 or len(raw) > 10:
            return await interaction.response.send_message("Provide 2‑10 options.", ephemeral=True)

        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)
        embed = build_poll_embed(question, raw, end_time, {opt: 0 for opt in raw})
        view = PollView(question, raw, end_time, interaction.guild_id)

        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        active_polls[msg.id] = {"message": msg, "view": view, "end_time": end_time}
        asyncio.create_task(auto_close_poll(msg.id))

async def setup(bot):
    await bot.add_cog(Poll(bot))