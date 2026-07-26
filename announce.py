import discord
from discord import app_commands
from discord.ext import commands
from formatter import BotEmbed
from checks import admin_only  # ensure checks.py is in root

class Announce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="announce", description="Send a professional announcement embed")
    @app_commands.describe(
        title="Title of the announcement",
        description="Main text of the announcement",
        channel="Channel to send the announcement (default: current)",
        color="Hex color (e.g. #3B82F6, default: blue)",
        image_url="URL of a large image at the bottom (optional)",
        thumbnail_url="URL of a small image top‑right (optional)",
        footer="Footer text (optional)"
    )
    @admin_only()
    async def announce(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        channel: discord.TextChannel = None,
        color: str = None,
        image_url: str = None,
        thumbnail_url: str = None,
        footer: str = None,
    ):
        # Always defer to ensure a response can be sent
        await interaction.response.defer(ephemeral=True)

        target_channel = channel or interaction.channel

        # Parse colour
        embed_color = discord.Color.blue()  # default
        if color:
            try:
                embed_color = discord.Color.from_str(color)
            except:
                embed = BotEmbed.error("Invalid Color", f"`{color}` is not a valid hex color. Use #3B82F6 format.")
                return await interaction.followup.send(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )
        if image_url:
            embed.set_image(url=image_url)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if footer:
            embed.set_footer(text=footer)

        try:
            await target_channel.send(embed=embed)
        except discord.Forbidden:
            embed_err = BotEmbed.error("Permission Denied", "I can't send messages in that channel.")
            return await interaction.followup.send(embed=embed_err, ephemeral=True)
        except Exception as e:
            embed_err = BotEmbed.error("Unexpected Error", f"Failed to send: {e}")
            return await interaction.followup.send(embed=embed_err, ephemeral=True)

        await interaction.followup.send(
            embed=BotEmbed.success("Announcement Sent", f"Posted in {target_channel.mention}."),
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Announce(bot))