import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from formatter import BotEmbed
from checks import is_extra_owner  # we’ll add this helper to checks.py

class DMAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Confirmation view with Yes/No buttons
    class ConfirmView(discord.ui.View):
        def __init__(self, cog, embed, guild, author):
            super().__init__(timeout=30)
            self.cog = cog
            self.embed = embed
            self.guild = guild
            self.author = author
            self.value = None

        @discord.ui.button(label="✅ Yes, send to everyone", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("This is not your command.", ephemeral=True)
                return
            self.value = True
            self.stop()
            await interaction.response.edit_message(view=None)
            await self.cog.send_dm_all(interaction, self.guild, self.embed)

        @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("This is not your command.", ephemeral=True)
                return
            self.value = False
            self.stop()
            await interaction.response.edit_message(view=None)

    @app_commands.command(name="dmall", description="Send an embed to every member in the server")
    @app_commands.describe(
        title="Embed title",
        description="Embed description",
        color="Hex color (e.g., #3B82F6)",
        image_url="Image URL (optional)",
        thumbnail_url="Thumbnail URL (optional)",
        footer="Footer text (optional)"
    )
    async def dmall(self, interaction: discord.Interaction,
                    title: str, description: str, color: str = None,
                    image_url: str = None, thumbnail_url: str = None, footer: str = None):
        # Only server owner or extra owners
        if interaction.user.id != interaction.guild.owner_id:
            if not await is_extra_owner(interaction.guild_id, interaction.user.id):
                embed = BotEmbed.error("Permission Denied", "Only the server owner or extra owners can use this.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Build the embed
        embed_color = discord.Color.blue()
        if color:
            try:
                embed_color = discord.Color.from_str(color)
            except:
                embed = BotEmbed.error("Invalid Color", f"`{color}` is not a valid hex color.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        dm_embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )
        if image_url:
            dm_embed.set_image(url=image_url)
        if thumbnail_url:
            dm_embed.set_thumbnail(url=thumbnail_url)
        if footer:
            dm_embed.set_footer(text=footer)

        # Ask for confirmation
        confirm_view = self.ConfirmView(self, dm_embed, interaction.guild, interaction.user)
        await interaction.response.send_message(
            "Are you sure you want to send this embed to **every member**?",
            embed=dm_embed,
            view=confirm_view,
            ephemeral=True
        )
        await confirm_view.wait()
        if confirm_view.value is None:
            await interaction.edit_original_response(content="Timed out.", embed=None, view=None)

    async def send_dm_all(self, interaction, guild, embed):
        members = guild.members
        total = len(members)
        sent = 0
        failed = 0
        status_msg = await interaction.followup.send(f"📤 Sending DMs… (0/{total})", ephemeral=True)

        for i, member in enumerate(members):
            if member.bot:
                continue
            try:
                await member.send(embed=embed)
                sent += 1
            except discord.Forbidden:
                failed += 1
            except Exception:
                failed += 1
            # Update progress every 10 members
            if (i + 1) % 10 == 0:
                await status_msg.edit(content=f"📤 Sending DMs… ({i+1}/{total})")
            await asyncio.sleep(0.5)  # prevent rate limits

        result = BotEmbed.success("DM All Completed", f"**Sent:** {sent}\n**Failed:** {failed}")
        await status_msg.edit(content=None, embed=result)

async def setup(bot):
    await bot.add_cog(DMAll(bot))