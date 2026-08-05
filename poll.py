import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Button

class PollModal(Modal, title="Create Poll"):
    def __init__(self, question: str):
        super().__init__()
        self.question = question
        self.option_inputs = []
        for i in range(1, 11):
            ti = TextInput(
                label=f"Option {i}",
                placeholder="Leave empty to skip",
                required=False,
                max_length=50,
                custom_id=f"option_{i}"
            )
            self.option_inputs.append(ti)
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        options = [ti.value.strip() for ti in self.option_inputs if ti.value and ti.value.strip()]
        if len(options) < 2:
            await interaction.response.send_message("You must provide at least 2 options.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊 {self.question}", color=0x3B82F6)
        embed.description = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
        embed.set_footer(text="Click a button to vote!")

        view = PollView(options)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

class PollView(View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.options = options
        self.votes = {opt: set() for opt in options}
        self.voters = set()

        for i, opt in enumerate(options):
            button = Button(
                label=f"{i+1}. {opt[:30]}",
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_opt_{i}"
            )
            button.callback = self.make_callback(i)
            self.add_item(button)

    def make_callback(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.voters:
                await interaction.response.send_message("You already voted!", ephemeral=True)
                return
            opt = self.options[idx]
            self.votes[opt].add(interaction.user.id)
            self.voters.add(interaction.user.id)
            embed = interaction.message.embeds[0]
            embed.description = "\n".join(f"{i+1}. {o} ({len(self.votes[o])} votes)" for i, o in enumerate(self.options))
            await interaction.message.edit(embed=embed)
            await interaction.response.defer(ephemeral=True)
        return callback

class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll with up to 10 options")
    @app_commands.describe(question="The poll question")
    async def poll_create(self, interaction: discord.Interaction, question: str):
        modal = PollModal(question)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(Poll(bot))