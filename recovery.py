import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from checks import admin_only
from formatter import BotEmbed

class Recovery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="recover", description="Clean up after a nuke – deletes all channels, kicks bots, removes webhooks")
    @app_commands.describe(keep_channel="Keep this channel?", kick_bots="Kick all bots?", kick_bot_id="Optional: Kick specific bot ID")
    @admin_only()
    @app_commands.checks.cooldown(1, 300.0) # 🛑 1 use per 5 minutes
    async def recover(self, interaction: discord.Interaction, keep_channel: bool = True, kick_bots: bool = True, kick_bot_id: str = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        cleaned = 0

        # 1. Delete all channels
        for channel in guild.channels:
            if keep_channel and channel.id == interaction.channel_id:
                continue
            try:
                await channel.delete(reason="Nuke recovery")
                cleaned += 1
                await asyncio.sleep(2) # 🛑 PREVENT RATE LIMIT
            except:
                pass

        # 2. Kick bots
        kicked = 0
        if kick_bots or kick_bot_id:
            # Safely parse ID to prevent ValueError crash
            target_bot_id = None
            if kick_bot_id:
                if kick_bot_id.isdigit():
                    target_bot_id = int(kick_bot_id)
                else:
                    # If they passed a mention like <@1234>, extract digits
                    target_bot_id = int(''.join(filter(str.isdigit, kick_bot_id)))
            
            for member in guild.members:
                if member.bot and member.id != self.bot.user.id:
                    if target_bot_id and member.id != target_bot_id:
                        continue
                    try:
                        await guild.kick(member, reason="Nuke recovery")
                        kicked += 1
                        await asyncio.sleep(1.5) # 🛑 PREVENT RATE LIMIT
                    except:
                        pass

        # 3. Delete webhooks
        for channel in guild.channels:
            try:
                webhooks = await channel.webhooks()
                for wh in webhooks:
                    await wh.delete(reason="Nuke recovery")
                    await asyncio.sleep(1.5) # 🛑 PREVENT RATE LIMIT
            except:
                pass

        await interaction.followup.send(
            f"✅ Recovery complete.\nChannels deleted: {cleaned}\nBots kicked: {kicked}\nAll webhooks removed.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Recovery(bot))