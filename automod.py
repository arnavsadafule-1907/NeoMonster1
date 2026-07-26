import discord
from discord import app_commands
from discord.ext import commands
from checks import admin_only
from formatter import BotEmbed

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.filtered_words = {}
        self.invite_block = {}
        self.spam_detection = {}
        self.spam_cache = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        guild_id = message.guild.id
        # Word filter
        words = self.filtered_words.get(guild_id, [])
        if words:
            content = message.content.lower()
            for word in words:
                if word.lower() in content:
                    try:
                        await message.delete()
                        await message.author.send(embed=BotEmbed.warning("Message Filtered", f"Your message in **{message.guild.name}** contained a filtered word."))
                    except:
                        pass
                    return
        # Invite blocker
        if self.invite_block.get(guild_id, False):
            if "discord.gg/" in message.content or "discord.com/invite/" in message.content:
                try:
                    await message.delete()
                    await message.author.send(embed=BotEmbed.warning("Invite Blocked", "Invite links are not allowed in that server."))
                except:
                    pass
                return
        # Spam detection
        if self.spam_detection.get(guild_id, False):
            now = discord.utils.utcnow().timestamp()
            cache = self.spam_cache.setdefault(guild_id, {}).setdefault(message.author.id, [])
            cache = [t for t in cache if now - t < 5]
            cache.append(now)
            self.spam_cache[guild_id][message.author.id] = cache
            if len(cache) >= 5:
                try:
                    await message.author.timeout(discord.utils.utcnow() + discord.timedelta(minutes=5), reason="Spam")
                    await message.channel.send(embed=BotEmbed.warning("Spam Detected", f"{message.author.mention} has been muted for spamming."))
                except:
                    pass

    @app_commands.command(name="automod", description="Configure automod")
    @app_commands.describe(action="Setting to change", word="Word for add/remove")
    @app_commands.choices(action=[
        app_commands.Choice(name="spam on", value="spam_on"),
        app_commands.Choice(name="spam off", value="spam_off"),
        app_commands.Choice(name="invites on", value="invites_on"),
        app_commands.Choice(name="invites off", value="invites_off"),
        app_commands.Choice(name="words add", value="words_add"),
        app_commands.Choice(name="words remove", value="words_remove"),
        app_commands.Choice(name="words list", value="words_list"),
    ])
    @admin_only()
    async def automod(self, interaction: discord.Interaction, action: str, word: str = None):
        guild_id = interaction.guild_id
        if action == "spam_on":
            self.spam_detection[guild_id] = True
            embed = BotEmbed.success("Spam Detection", "Enabled.")
        elif action == "spam_off":
            self.spam_detection[guild_id] = False
            embed = BotEmbed.success("Spam Detection", "Disabled.")
        elif action == "invites_on":
            self.invite_block[guild_id] = True
            embed = BotEmbed.success("Invite Blocking", "Enabled.")
        elif action == "invites_off":
            self.invite_block[guild_id] = False
            embed = BotEmbed.success("Invite Blocking", "Disabled.")
        elif action == "words_add":
            if not word:
                embed = BotEmbed.error("Missing Word", "You must provide a word.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            self.filtered_words.setdefault(guild_id, []).append(word.lower())
            embed = BotEmbed.success("Word Added", f"`{word}` added to the filter.")
        elif action == "words_remove":
            if not word:
                embed = BotEmbed.error("Missing Word", "You must provide a word.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            lst = self.filtered_words.get(guild_id, [])
            if word.lower() in lst:
                lst.remove(word.lower())
                embed = BotEmbed.success("Word Removed", f"`{word}` removed from filter.")
            else:
                embed = BotEmbed.error("Not Found", "Word not in filter.")
        elif action == "words_list":
            lst = self.filtered_words.get(guild_id, [])
            text = ", ".join(lst) if lst else "No filtered words."
            embed = BotEmbed.info("Filtered Words", text)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Automod(bot))