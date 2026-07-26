import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class Welcoming(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channels = {}
        self.welcome_messages = {}
        self.farewell_channels = {}
        self.auto_roles = {}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild_id = member.guild.id
        role_id = self.auto_roles.get(guild_id)
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass
        channel_id = self.welcome_channels.get(guild_id)
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                msg = self.welcome_messages.get(guild_id, "Welcome {user}!")
                msg = msg.replace("{user}", member.mention).replace("{server}", member.guild.name)
                await channel.send(msg)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild_id = member.guild.id
        channel_id = self.farewell_channels.get(guild_id)
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                await channel.send(f"👋 {member.mention} has left the server.")

    @app_commands.command(name="welcome", description="Configure welcome settings")
    @app_commands.describe(action="Setting to change", channel="Target channel", message="Welcome message", role="Auto role")
    @app_commands.choices(action=[
        app_commands.Choice(name="channel", value="channel"),
        app_commands.Choice(name="message", value="message"),
        app_commands.Choice(name="role", value="role"),
        app_commands.Choice(name="test", value="test"),
    ])
    @admin_only()
    async def welcome(self, interaction: discord.Interaction, action: str, channel: discord.TextChannel = None, message: str = None, role: discord.Role = None):
        guild_id = interaction.guild_id
        if action == "channel":
            if not channel:
                embed = BotEmbed.error("Missing Channel", "Please specify a text channel.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            self.welcome_channels[guild_id] = channel.id
            embed = BotEmbed.success("Welcome Channel", f"Set to {channel.mention}.")
        elif action == "message":
            if not message:
                embed = BotEmbed.error("Missing Message", "Provide a welcome message.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            self.welcome_messages[guild_id] = message
            embed = BotEmbed.success("Welcome Message", "Message updated.")
        elif action == "role":
            if not role:
                embed = BotEmbed.error("Missing Role", "Mention a role to auto-assign.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            self.auto_roles[guild_id] = role.id
            embed = BotEmbed.success("Auto Role", f"{role.mention} will be assigned to new members.")
        elif action == "test":
            channel_id = self.welcome_channels.get(guild_id)
            if not channel_id:
                embed = BotEmbed.error("Not Set", "Welcome channel is not configured.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                msg = self.welcome_messages.get(guild_id, "Welcome {user}!")
                msg = msg.replace("{user}", interaction.user.mention).replace("{server}", interaction.guild.name)
                await channel.send(msg)
                embed = BotEmbed.success("Test Sent", "Welcome message test sent.")
            else:
                embed = BotEmbed.error("Channel Not Found", "The saved channel no longer exists.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="farewell", description="Set farewell channel")
    @app_commands.describe(channel="Channel for leave messages")
    @admin_only()
    async def farewell(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.farewell_channels[interaction.guild_id] = channel.id
        embed = BotEmbed.success("Farewell Channel", f"Set to {channel.mention}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Welcoming(bot))