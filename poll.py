import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import asyncio
from datetime import datetime, timezone, timedelta
from checks import staff_only

active_polls = {}   # poll_id -> {"message": msg, "view": view, "end_time": datetime}

class PollView(View):
    def __init__(self, options, question, end_time):
        super().__init__(timeout=None)
        self.options = options
        self.question = question
        self.end_time = end_time
        self.votes = {opt: set() for opt in options}
        self.voters = set()
        self.message = None   # set after sending

        # Vote buttons (one per option)
        for i, opt in enumerate(options):
            button = Button(
                label=f"{i+1}. {opt[:30]}",
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_opt_{i}"
            )
            button.callback = self.make_vote_callback(i)
            self.add_item(button)

        # "Show Results" button
        results_button = Button(
            label="📊 Show Results",
            style=discord.ButtonStyle.secondary,
            custom_id="poll_results"
        )
        results_button.callback = self.show_results_callback
        self.add_item(results_button)

    def make_vote_callback(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.voters:
                await interaction.response.send_message("You already voted!", ephemeral=True)
                return
            opt = self.options[idx]
            self.votes[opt].add(interaction.user.id)
            self.voters.add(interaction.user.id)
            embed = build_poll_embed(self.question, self.options, self.end_time, votes=self.votes)
            await interaction.message.edit(embed=embed)
            await interaction.response.defer(ephemeral=True)
        return callback

    async def show_results_callback(self, interaction: discord.Interaction):
        results = []
        total = len(self.voters)
        for i, opt in enumerate(self.options):
            voters = self.votes[opt]
            if voters:
                voter_mentions = ", ".join(f"<@{uid}>" for uid in voters)
                results.append(f"**{i+1}. {opt}** ({len(voters)}): {voter_mentions}")
            else:
                results.append(f"**{i+1}. {opt}** (0)")
        embed = discord.Embed(title=f"📊 {self.question} – Results", color=0x3B82F6)
        embed.description = "\n".join(results) if results else "No votes yet."
        embed.set_footer(text=f"Total voters: {total}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def close_poll(self):
        for child in self.children:
            child.disabled = True
        embed = build_poll_embed(self.question, self.options, self.end_time, votes=self.votes)
        embed.set_footer(text="Poll closed")
        if self.message:
            await self.message.edit(embed=embed, view=self)


async def auto_close_poll(poll_id):
    await asyncio.sleep(0.5)
    if poll_id not in active_polls:
        return
    data = active_polls[poll_id]
    now = discord.utils.utcnow()
    wait_seconds = (data["end_time"] - now).total_seconds()
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)
    view = data["view"]
    view.message = data["message"]
    await view.close_poll()
    active_polls.pop(poll_id, None)


def build_poll_embed(question, options, end_time, votes=None):
    if votes is None:
        votes = {opt: set() for opt in options}
    total_voters = len(set().union(*votes.values()))
    remaining = end_time - discord.utils.utcnow()
    if remaining.total_seconds() > 0:
        remaining_str = f"{remaining.seconds//60}m {remaining.seconds%60}s"
    else:
        remaining_str = "Closed"
    description = "\n".join(f"{i+1}. {opt} ({len(votes[opt])} votes)" for i, opt in enumerate(options))
    description += f"\n\n**Total voters:** {total_voters} | **Time left:** {remaining_str}"
    embed = discord.Embed(title=f"📊 {question}", description=description, color=0x3B82F6)
    embed.set_footer(text=f"Poll ends at {end_time.strftime('%H:%M UTC')} • Click a button to vote!")
    return embed


class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll (comma‑separated options, max 10)")
    @app_commands.describe(
        question="The poll question",
        options="Comma‑separated options, e.g. 'Red, Green, Blue' (max 10)",
        duration="Duration in minutes (1-1440)"
    )
    @staff_only()
    async def poll_create(self, interaction: discord.Interaction, question: str, options: str, duration: int):
        if duration < 1 or duration > 1440:
            await interaction.response.send_message("Duration must be between 1 and 1440 minutes.", ephemeral=True)
            return

        # Parse comma‑separated options
        raw_opts = [opt.strip() for opt in options.split(",") if opt.strip()]
        if len(raw_opts) < 2:
            await interaction.response.send_message("You must provide at least 2 options.", ephemeral=True)
            return
        if len(raw_opts) > 10:
            raw_opts = raw_opts[:10]  # silently truncate

        end_time = discord.utils.utcnow() + timedelta(minutes=duration)
        embed = build_poll_embed(question, raw_opts, end_time)
        view = PollView(raw_opts, question, end_time)

        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()

        # Store for auto-close
        poll_id = msg.id
        active_polls[poll_id] = {
            "message": msg,
            "view": view,
            "end_time": end_time
        }
        asyncio.create_task(auto_close_poll(poll_id))

        # Log poll creation
        logger_cog = self.bot.get_cog("ServerLogger")
        if logger_cog:
            await logger_cog.log_poll_action(interaction.guild, interaction.user, "create", question=question, channel=interaction.channel)


async def setup(bot):
    await bot.add_cog(Poll(bot))