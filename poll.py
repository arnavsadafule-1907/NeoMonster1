import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import asyncio
from datetime import datetime, timezone, timedelta
from checks import staff_only

# In‑memory storage
active_polls = {}   # poll_id -> {"message": msg, "view": PollView, "end_time": datetime}

# ---------- Embed Builder ----------
def build_poll_embed(question: str, options: list, end_time: datetime, votes: dict = None):
    if votes is None:
        votes = {opt: 0 for opt in options}  # option -> count

    total = sum(votes.values())
    remaining = end_time - datetime.now(timezone.utc)
    if remaining.total_seconds() > 0:
        remaining_str = f"{remaining.seconds // 60}m {remaining.seconds % 60}s"
    else:
        remaining_str = "⏰ Closed"

    embed = discord.Embed(
        title=f"📊 {question}",
        color=0x3B82F6,
        timestamp=end_time
    )

    for i, opt in enumerate(options):
        count = votes.get(opt, 0)
        percent = (count / total * 100) if total > 0 else 0
        bar_len = 12
        filled = int(round(percent / 100 * bar_len))
        bar = "█" * filled + "░" * (bar_len - filled)
        embed.add_field(
            name=f"**{i+1}. {opt}**",
            value=f"`{count}` votes  ({percent:.1f}%)  {bar}",
            inline=False
        )

    embed.set_footer(
        text=f"Total votes: {total}  •  Time left: {remaining_str}  •  Click a button to vote"
    )
    return embed


# ---------- Poll View ----------
class PollView(View):
    def __init__(self, question: str, options: list, end_time: datetime):
        super().__init__(timeout=None)
        self.question = question
        self.options = options
        self.end_time = end_time
        self.votes = {opt: 0 for opt in options}   # option -> count
        self.voter_choice = {}   # user_id -> option
        self.message = None

        # Create one button per option (max 10, Discord allows 5 per row, so we'll auto-split into rows of 5)
        for i, opt in enumerate(options):
            button = Button(
                label=opt,
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_opt_{i}"
            )
            button.callback = self.make_callback(opt)
            # Add to view – Discord automatically wraps after 5 buttons per row
            self.add_item(button)

        # "Show Results" button (staff only)
        results_button = Button(
            label="📊 Show Results",
            style=discord.ButtonStyle.secondary,
            custom_id="poll_results"
        )
        results_button.callback = self.show_results_callback
        self.add_item(results_button)

    def make_callback(self, option):
        async def callback(interaction: discord.Interaction):
            user = interaction.user

            # If user already voted, remove their old vote
            if user.id in self.voter_choice:
                old = self.voter_choice[user.id]
                self.votes[old] -= 1

            # Record new vote
            self.votes[option] += 1
            self.voter_choice[user.id] = option

            # Update embed
            embed = build_poll_embed(self.question, self.options, self.end_time, self.votes)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message(
                f"✅ You voted for **{option}**.",
                ephemeral=True
            )
        return callback

    async def show_results_callback(self, interaction: discord.Interaction):
        if not await self._is_staff(interaction):
            await interaction.response.send_message("Only staff can view detailed results.", ephemeral=True)
            return

        lines = []
        for opt in self.options:
            count = self.votes.get(opt, 0)
            voters = [uid for uid, choice in self.voter_choice.items() if choice == opt]
            if voters:
                mentions = ", ".join(f"<@{uid}>" for uid in voters)
                lines.append(f"**{opt}** – {count} votes: {mentions}")
            else:
                lines.append(f"**{opt}** – 0 votes")

        embed = discord.Embed(
            title=f"📊 Detailed Results – {self.question}",
            description="\n".join(lines),
            color=0x3B82F6
        )
        embed.set_footer(text=f"Total voters: {len(self.voter_choice)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _is_staff(self, interaction: discord.Interaction) -> bool:
        allowed_roles = ["TicketSupporter", "Staff.exe", "admin.exe", "nuke.exe"]
        for role_name in allowed_roles:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in interaction.user.roles:
                return True
        return False

    async def close_poll(self):
        for child in self.children:
            child.disabled = True
        embed = build_poll_embed(self.question, self.options, self.end_time, self.votes)
        embed.set_footer(text="⏰ Poll closed • Results finalised")
        if self.message:
            await self.message.edit(embed=embed, view=self)


# ---------- Auto‑close background task ----------
async def auto_close_poll(poll_id: int):
    await asyncio.sleep(0.5)
    if poll_id not in active_polls:
        return
    data = active_polls[poll_id]
    now = datetime.now(timezone.utc)
    wait_seconds = (data["end_time"] - now).total_seconds()
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)
    view = data["view"]
    view.message = data["message"]
    await view.close_poll()
    active_polls.pop(poll_id, None)


# ---------- Cog ----------
class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a professional poll (staff only)")
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

        raw_opts = [opt.strip() for opt in options.split(",") if opt.strip()]
        if len(raw_opts) < 2:
            await interaction.response.send_message("You must provide at least 2 options.", ephemeral=True)
            return
        if len(raw_opts) > 10:
            raw_opts = raw_opts[:10]

        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)
        embed = build_poll_embed(question, raw_opts, end_time)
        view = PollView(question, raw_opts, end_time)

        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()

        poll_id = msg.id
        active_polls[poll_id] = {
            "message": msg,
            "view": view,
            "end_time": end_time
        }
        asyncio.create_task(auto_close_poll(poll_id))

        # Optional logging
        logger_cog = self.bot.get_cog("ServerLogger")
        if logger_cog:
            await logger_cog.log_poll_action(interaction.guild, interaction.user, "create", question=question, channel=interaction.channel)


async def setup(bot):
    await bot.add_cog(Poll(bot))