import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from checks import admin_only          # <-- new import

class Recovery(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="recover", description="Clean up after a nuke – deletes all channels, kicks bots, removes webhooks")
    @app_commands.describe(
        keep_channel="Keep this channel? (default: the channel where command is used)",
        kick_bots="Kick all bots? (default: True)",
        kick_bot_id="Optional: Kick a specific bot by ID only"
    )
    @admin_only()                      # <-- now requires admin.exe / nuke.exe / owner
    async def recover(
        self,
        interaction: discord.Interaction,
        keep_channel: bool = True,
        kick_bots: bool = True,
        kick_bot_id: str = None
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        cleaned = 0

        # 1. Delete all channels except maybe the current one
        for channel in guild.channels:
            if keep_channel and channel.id == interaction.channel_id:
                continue
            try:
                await channel.delete(reason="Nuke recovery")
                cleaned += 1
                await asyncio.sleep(0.3)  # slight delay to avoid rate limits
            except:
                pass

        # 2. Kick bots
        kicked = 0
        if kick_bots or kick_bot_id:
            target_bot_id = int(kick_bot_id) if kick_bot_id else None
            for member in guild.members:
                if member.bot and member.id != self.bot.user.id:  # don't kick our own bot
                    if target_bot_id and member.id != target_bot_id:
                        continue
                    try:
                        await guild.kick(member, reason="Nuke recovery")
                        kicked += 1
                    except:
                        pass

        # 3. Delete all webhooks
        for channel in guild.channels:
            try:
                webhooks = await channel.webhooks()
                for wh in webhooks:
                    await wh.delete(reason="Nuke recovery")
            except:
                pass

        await interaction.followup.send(
            f"✅ Recovery complete.\n"
            f"Channels deleted: {cleaned}\n"
            f"Bots kicked: {kicked}\n"
            f"All webhooks removed.\n"
            f"Use Server Settings → Roles to remove the nuker’s roles manually if needed.",
            ephemeral=False
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Recovery(bot))