import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class Boycott(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vcban", description="Ban a user from all voice channels")
    @app_commands.describe(member="Member to voice ban")
    @admin_only()
    async def vcban(self, interaction: discord.Interaction, member: discord.Member):
        if member.voice and member.voice.channel:
            await member.move_to(None, reason="VC ban")
        count = 0
        for channel in interaction.guild.voice_channels:
            await channel.set_permissions(member, connect=False)
            count += 1
        embed = BotEmbed.success("Voice Ban", f"{member.mention} has been voice banned from {count} channels.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unvcban", description="Remove voice ban")
    @app_commands.describe(member="Member to unban")
    @admin_only()
    async def unvcban(self, interaction: discord.Interaction, member: discord.Member):
        for channel in interaction.guild.voice_channels:
            await channel.set_permissions(member, connect=None)
        embed = BotEmbed.success("Voice Ban Removed", f"{member.mention} can join voice channels again.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="boycott", description="Boycott (ban) a user")
    @app_commands.describe(user="User to boycott")
    @admin_only()
    async def boycott(self, interaction: discord.Interaction, user: discord.User):
        try:
            await interaction.guild.ban(user, reason="Boycott", delete_message_days=0)
            embed = BotEmbed.success("Boycott", f"{user.mention} has been boycotted (banned).")
        except Exception as e:
            embed = BotEmbed.error("Failed", str(e))
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Boycott(bot))