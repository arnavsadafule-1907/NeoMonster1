import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from checks import owner_only


class Recovery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="recover", description="Clean up after a nuke – deletes all channels, kicks bots, removes webhooks")
    @app_commands.describe(keep_channel="Keep this channel?", kick_bots="Kick all bots?", kick_bot_id="Optional: Kick specific bot ID")
    @owner_only()
    @app_commands.checks.cooldown(1, 300.0)
    async def recover(self, interaction: discord.Interaction, keep_channel: bool = True, kick_bots: bool = True, kick_bot_id: str | None = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return
        cleaned = 0

        for channel in guild.channels:
            if keep_channel and channel.id == interaction.channel_id:
                continue
            try:
                await channel.delete(reason="Nuke recovery")
                cleaned += 1
                await asyncio.sleep(1.5)
            except (discord.Forbidden, discord.HTTPException):
                pass

        kicked = 0
        if kick_bots or kick_bot_id:
            target_bot_id = None
            if kick_bot_id:
                clean_id = ''.join(filter(str.isdigit, kick_bot_id))
                if clean_id:
                    target_bot_id = int(clean_id)

            for member in guild.members:
                if member.bot and member.id != self.bot.user.id:
                    if target_bot_id and member.id != target_bot_id:
                        continue
                    try:
                        await guild.kick(member, reason="Nuke recovery")
                        kicked += 1
                        await asyncio.sleep(1.5)
                    except (discord.Forbidden, discord.HTTPException):
                        pass

        for channel in guild.channels:
            try:
                webhooks = await channel.webhooks()
                for wh in webhooks:
                    await wh.delete(reason="Nuke recovery")
                    await asyncio.sleep(1.0)
            except (discord.Forbidden, discord.HTTPException):
                pass

        prefix = "✅ "
        await interaction.followup.send(
            f"{prefix}Recovery complete.\nChannels deleted: {cleaned}\nBots kicked: {kicked}\nAll webhooks removed.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Recovery(bot))
