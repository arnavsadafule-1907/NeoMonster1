import discord
from discord import app_commands
from discord.ext import commands

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sync", description="Force sync all slash commands (owner only)")
    async def sync_commands(self, interaction: discord.Interaction):
        if interaction.user.id not in self.bot.owner_ids:
            await interaction.response.send_message("Only the bot owner can use this.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"✅ Synced {len(synced)} commands globally.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Sync(bot))