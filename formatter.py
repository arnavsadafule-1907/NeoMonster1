import discord

class BotEmbed:
    @staticmethod
    def success(title: str, description: str = None, **kwargs) -> discord.Embed:
        embed = discord.Embed(title=title, color=discord.Color.green(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text="NeoMonster • Professional Security")
        return embed

    @staticmethod
    def error(title: str, description: str = None, **kwargs) -> discord.Embed:
        embed = discord.Embed(title=title, color=discord.Color.red(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text="NeoMonster • Error")
        return embed

    @staticmethod
    def info(title: str, description: str = None, **kwargs) -> discord.Embed:
        embed = discord.Embed(title=title, color=discord.Color.blue(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text="NeoMonster • Info")
        return embed

    @staticmethod
    def warning(title: str, description: str = None, **kwargs) -> discord.Embed:
        embed = discord.Embed(title=title, color=discord.Color.gold(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text="NeoMonster • Warning")
        return embed