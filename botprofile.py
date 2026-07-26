import discord
from discord import app_commands
from discord.ext import commands
from formatter import BotEmbed

class BotProfile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setbotbio", description="Set the bot's About Me (owner only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setbotbio(self, interaction: discord.Interaction):
        if interaction.user.id not in self.bot.owner_ids:
            embed = BotEmbed.error("Permission Denied", "Only the bot owner can change my bio.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        bio_text = await self._build_bio()
        await self._update_bio(bio_text, interaction)

    async def _build_bio(self) -> str:
        invite_url = "https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473378998&integration_type=0&scope=bot+applications.commands"
        bio = f"🛡️ Protecting servers 24/7 | Invite: {invite_url}"
        if len(bio) > 190:
            bio = f"🛡️ Server security | {invite_url}"
        return bio

    async def _update_bio(self, bio: str, interaction: discord.Interaction = None):
        """Try standard edit first, fallback to raw HTTP request."""
        try:
            await self.bot.user.edit(bio=bio)
            if interaction:
                embed = BotEmbed.success("Bio Updated", "My About Me now shows only the invite link.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except TypeError:
            # discord.py version too old – use raw HTTP patch
            try:
                route = discord.http.Route('PATCH', '/users/@me')
                await self.bot.http.request(route, json={'bio': bio})
                if interaction:
                    embed = BotEmbed.success("Bio Updated", "My About Me has been updated (using fallback method).")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                if interaction:
                    embed = BotEmbed.error("Failed to Update Bio", str(e))
                    await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            if interaction:
                embed = BotEmbed.error("Failed to Update Bio", str(e))
                await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.owner_ids:
            try:
                bio = await self._build_bio()
                await self._update_bio(bio)   # no interaction on startup
            except Exception as e:
                print(f"Failed to auto‑update bot bio: {e}")

async def setup(bot):
    await bot.add_cog(BotProfile(bot))