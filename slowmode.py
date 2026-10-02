import discord
from discord import app_commands
from discord.ext import commands
from formatter import BotEmbed
from checks import staff_only


class Slowmode(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slowmode", description="Set slowmode for all text channels")
    @app_commands.describe(seconds="Slowmode duration (0 to disable)", reason="Reason for slowmode")
    @staff_only()
    async def slowmode_all(self, interaction: discord.Interaction, seconds: int, reason: str = "No reason provided"):
        if seconds < 0 or seconds > 21600:
            embed = BotEmbed.error("Invalid Duration", "Slowmode must be between 0 and 21600 seconds.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        await interaction.response.defer(ephemeral=True)
        count = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.edit(slowmode_delay=seconds, reason=reason)
                count += 1
            except:
                pass

        if seconds == 0:
            embed = BotEmbed.success("Slowmode Disabled", f"Removed slowmode from {count} channels.")
        else:
            embed = BotEmbed.success("Slowmode Enabled", f"Set {seconds}s slowmode in {count} channels.")
        await interaction.followup.send(embed=embed, ephemeral=False)


async def setup(bot):
    await bot.add_cog(Slowmode(bot))