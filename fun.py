import discord
from discord import app_commands
from discord.ext import commands
import random
import urllib.request
import json
from formatter import BotEmbed

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Ask the magic 8ball")
    @app_commands.describe(question="Your question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        answers = ["Yes.", "No.", "Maybe.", "Ask again later.", "Definitely!", "I doubt it."]
        embed = BotEmbed.info("8ball", f"🎱 {random.choice(answers)}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="meme", description="Random meme")
    async def meme(self, interaction: discord.Interaction):
        try:
            # Use standard library urllib instead of requests
            req = urllib.request.Request("https://meme-api.com/gimme")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
            embed = BotEmbed.info(data["title"])
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"👍 {data['ups']} | r/{data['subreddit']}")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            embed = BotEmbed.error("Error", "Could not fetch meme.")
            await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="rps", description="Rock-Paper-Scissors")
    @app_commands.describe(choice="Your choice")
    @app_commands.choices(choice=[
        app_commands.Choice(name="rock", value="rock"),
        app_commands.Choice(name="paper", value="paper"),
        app_commands.Choice(name="scissors", value="scissors"),
    ])
    async def rps(self, interaction: discord.Interaction, choice: str):
        bot_choice = random.choice(["rock", "paper", "scissors"])
        win = (choice == "rock" and bot_choice == "scissors") or \
              (choice == "paper" and bot_choice == "rock") or \
              (choice == "scissors" and bot_choice == "paper")
        if choice == bot_choice:
            result = "It's a tie!"
        elif win:
            result = "You win!"
        else:
            result = "You lose!"
        embed = BotEmbed.info("Rock-Paper-Scissors", f"You chose **{choice}**, I chose **{bot_choice}**. {result}")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Fun(bot))