import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="voicestats", description="Voice activity stats")
    @app_commands.describe(member="Member to check")
    async def voicestats(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        if member.voice and member.voice.channel:
            mute = member.voice.mute or member.voice.self_mute
            deaf = member.voice.deaf or member.voice.self_deaf
            embed = BotEmbed.info("Voice Stats", f"{member.mention} is in **{member.voice.channel.name}** | Muted: {mute} | Deafened: {deaf}")
        else:
            embed = BotEmbed.warning("Not Connected", f"{member.mention} is not in a voice channel.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vc", description="Voice management")
    @app_commands.describe(action="Action", member="Target member")
    @app_commands.choices(action=[
        app_commands.Choice(name="kick", value="kick"),
        app_commands.Choice(name="mute", value="mute"),
    ])
    @admin_only()
    async def vc(self, interaction: discord.Interaction, action: str, member: discord.Member):
        if not member.voice or not member.voice.channel:
            embed = BotEmbed.error("Not in Voice", f"{member.mention} is not in a voice channel.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        if action == "kick":
            await member.move_to(None, reason="VC kick")
            embed = BotEmbed.success("Voice Kick", f"{member.mention} has been kicked from voice.")
        elif action == "mute":
            await member.edit(mute=True, reason="VC mute")
            embed = BotEmbed.success("Voice Mute", f"{member.mention} has been muted in voice.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Voice(bot))