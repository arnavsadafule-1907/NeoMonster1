import discord
from discord.ext import commands

DEFAULT_RESPONSES = {
    "hello": "Hello! How can I help you?",
    "hi": "Hi there! 👋",
    "help": "Use `/help` to see all commands.",
    "invite": "You can invite me using the link in my profile!",
    "dashboard": "Our admin dashboard is private. Ask a staff member for access.",
    "rules": "Please check the #rules channel for server rules.",
    "apply": "To apply for staff, wait for application openings.",
    "ip": "This server doesn't have a game IP. This is a Discord community.",
}


class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.responses = DEFAULT_RESPONSES.copy()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if self.bot.user in message.mentions:
            content = message.content.replace(f"<@{self.bot.user.id}>", "").strip().lower()
            for trigger, response in self.responses.items():
                if trigger in content:
                    await message.channel.send(response)
                    return


async def setup(bot):
    await bot.add_cog(Chatbot(bot))