import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class Ignore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ignored_users = set()
        self.ignored_channels = set()

    @app_commands.command(name="ignore", description="Make the bot ignore a user or channel")
    @app_commands.describe(target_type="User or channel", user="User to ignore", channel="Channel to ignore")
    @app_commands.choices(target_type=[
        app_commands.Choice(name="user", value="user"),
        app_commands.Choice(name="channel", value="channel"),
    ])
    @admin_only()
    async def ignore(self, interaction: discord.Interaction, target_type: str, user: discord.User = None, channel: discord.TextChannel = None):
        if target_type == "user" and user:
            self.ignored_users.add(user.id)
            embed = BotEmbed.success("Ignored User", f"Now ignoring {user.mention}.")
        elif target_type == "channel" and channel:
            self.ignored_channels.add(channel.id)
            embed = BotEmbed.success("Ignored Channel", f"Now ignoring {channel.mention}.")
        else:
            embed = BotEmbed.error("Invalid Target", "Provide a user or channel.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unignore", description="Remove ignore")
    @app_commands.describe(target_type="User or channel", user="User to unignore", channel="Channel to unignore")
    @app_commands.choices(target_type=[
        app_commands.Choice(name="user", value="user"),
        app_commands.Choice(name="channel", value="channel"),
    ])
    @admin_only()
    async def unignore(self, interaction: discord.Interaction, target_type: str, user: discord.User = None, channel: discord.TextChannel = None):
        if target_type == "user" and user:
            self.ignored_users.discard(user.id)
            embed = BotEmbed.success("Unignored User", f"No longer ignoring {user.mention}.")
        elif target_type == "channel" and channel:
            self.ignored_channels.discard(channel.id)
            embed = BotEmbed.success("Unignored Channel", f"No longer ignoring {channel.mention}.")
        else:
            embed = BotEmbed.error("Invalid Target", "Provide a user or channel.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.user.id in self.ignored_users:
            if interaction.type == discord.InteractionType.application_command:
                await interaction.response.send_message(embed=BotEmbed.warning("Ignored", "You are being ignored by the bot."), ephemeral=True)
        if interaction.channel_id in self.ignored_channels:
            if interaction.type == discord.InteractionType.application_command:
                await interaction.response.send_message(embed=BotEmbed.warning("Ignored", "This channel is being ignored by the bot."), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Ignore(bot))