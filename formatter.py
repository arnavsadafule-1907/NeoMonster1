import discord


def get_emoji(name: str) -> str:
    return {
        "tick": "✅",
        "cross": "❌",
        "shield": "🛡️",
        "warning": "⚠️",
    }.get(name, "")


class BotEmbed:
    @staticmethod
    def success(title: str, description: str | None = None, **kwargs) -> discord.Embed:
        icon = get_emoji("tick")
        prefix = f"{icon} " if icon and not title.startswith(icon) else ""
        embed = discord.Embed(title=f"{prefix}{title}", color=discord.Color.green(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text=f"NeoMonster {get_emoji('shield')} Professional Security")
        return embed

    @staticmethod
    def error(title: str, description: str | None = None, **kwargs) -> discord.Embed:
        icon = get_emoji("cross")
        prefix = f"{icon} " if icon and not title.startswith(icon) else ""
        embed = discord.Embed(title=f"{prefix}{title}", color=discord.Color.red(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text=f"NeoMonster {get_emoji('cross')} Error")
        return embed

    @staticmethod
    def info(title: str, description: str | None = None, **kwargs) -> discord.Embed:
        icon = get_emoji("shield")
        prefix = f"{icon} " if icon and not title.startswith(icon) else ""
        embed = discord.Embed(title=f"{prefix}{title}", color=discord.Color.blue(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text=f"NeoMonster {get_emoji('shield')} Info")
        return embed

    @staticmethod
    def warning(title: str, description: str | None = None, **kwargs) -> discord.Embed:
        icon = get_emoji("warning")
        prefix = f"{icon} " if icon and not title.startswith(icon) else ""
        embed = discord.Embed(title=f"{prefix}{title}", color=discord.Color.gold(), **kwargs)
        if description:
            embed.description = description
        embed.set_footer(text=f"NeoMonster {get_emoji('warning')} Warning")
        return embed
