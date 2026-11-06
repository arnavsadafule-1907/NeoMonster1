import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from checks import admin_only
from formatter import BotEmbed

class Boycott(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vcban", description="Ban a user from all voice channels")
    @app_commands.describe(member="Member to voice ban")
    @admin_only()
    @app_commands.checks.cooldown(1, 10.0)
    async def vcban(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        if member.voice and member.voice.channel:
            try:
                await member.move_to(None, reason="VC ban")
            except Exception:
                pass

        count = 0
        for channel in interaction.guild.voice_channels:
            try:
                await channel.set_permissions(member, connect=False)
                count += 1
                await asyncio.sleep(0.5)
            except Exception:
                pass

        embed = BotEmbed.success("Voice Ban", f"{member.mention} has been voice banned from {count} channels.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="unvcban", description="Remove voice ban")
    @app_commands.describe(member="Member to unban")
    @admin_only()
    @app_commands.checks.cooldown(1, 10.0)
    async def unvcban(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        count = 0
        for channel in interaction.guild.voice_channels:
            try:
                await channel.set_permissions(member, connect=None)
                count += 1
                await asyncio.sleep(0.5)
            except Exception:
                pass

        embed = BotEmbed.success("Voice Ban Removed", f"{member.mention} can join {count} channels again.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="boycott", description="Boycott (ban) a user")
    @app_commands.describe(user="User to boycott")
    @admin_only()
    @app_commands.checks.cooldown(1, 5.0)
    async def boycott(self, interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            return
        member = interaction.guild.get_member(user.id)
        if member:
            if member >= interaction.guild.me.top_role:
                embed = BotEmbed.error("Role Too High", "I cannot ban this member because their role is higher than or equal to mine.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            if isinstance(interaction.user, discord.Member):
                if member >= interaction.user.top_role and interaction.user != interaction.guild.owner and interaction.user.id not in interaction.client.owner_ids:
                    embed = BotEmbed.error("Role Too High", "You cannot ban a member whose role is higher than or equal to yours.")
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await interaction.guild.ban(user, reason="Boycott", delete_message_days=0)
            embed = BotEmbed.success("Boycott", f"{user.mention} has been boycotted (banned).")
        except Exception as e:
            embed = BotEmbed.error("Failed", str(e))
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Boycott(bot))
