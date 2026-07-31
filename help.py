import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select

BLUE_MAIN = 0x3B82F6
BLUE_ACCENT = 0x60A5FA

class HelpView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=120)
        self.bot = bot
        self.current_page = 0
        self.message = None

        # Exact module list with blue‑themed emojis
        self.modules = [
            "🏠 Home",
            "🛡️ Antinuke Security",
            "🔒 Anti Betray",
            "🌐 Limit System",          # Blue Network icon
            "❌ Auto Emergency",        # Blue Cross icon
            "❌ Emergency",             # Blue Cross icon
            "🔧 Moderation",           # Blue Wrench icon
            "🔧 Utility",              # Blue Wrench icon
            "🔨 Automod",              # Blue Hammer icon
            "📬 Welcoming",            # Blue Mailbox icon
            "🔷 Customroles",          # Blue Diamond (star replacement)
            "☄️ Giveaway",             # Blue Comet/Blast icon
            "🔷 Boycott/VcBan",        # Blue Diamond + NEW badge
            "✅ Automations",          # Blue Check icon
            "👤 Fun",                  # Blue Profile icon
            "🎙️ Voice",               # Blue Mic icon
            "⚙️ Admin / Mod Setup",    # Blue Gear icon
            "⚙️ Ignore Commands",      # Blue Gear icon
        ]

        self.module_data = {
            "🏠 Home": {
                "description": "Advanced server security, automated moderation, and seamless community management — all in one powerful bot.",
                "commands": []
            },
            "🛡️ Antinuke Security": {
                "description": "Anti‑nuke, anti‑spam, lockdown & raid protection.",
                "commands": [
                    "`/antinuke settings` — View current security config",
                    "`/antinuke toggle` — Enable/disable anti‑nuke",
                    "`/antinuke emergency` — Lockdown or kick nukers",
                    "`/massmention` — Manage mass‑mention protection",
                    "`/antivanity` — Block custom invite links",
                ]
            },
            "🔒 Anti Betray": {
                "description": "Prevents trusted members from abusing power and betraying the server.",
                "commands": [
                    "`/antinuke whitelist add` — Add trusted admins",
                    "`/antinuke emergency kick_nuker` — Remove a rogue admin",
                ]
            },
            "🌐 Limit System": {
                "description": "Rate‑limit destructive actions to prevent mass spam and floods.",
                "commands": [
                    "`/antinuke threshold` — Set action limits",
                    "`/antinuke timewindow` — Detection time window",
                ]
            },
            "❌ Auto Emergency": {
                "description": "Automatically locks the server when a nuke is detected.",
                "commands": [
                    "`/antinuke emergency lock` — Manual lockdown",
                    "`/antinuke emergency unlock` — Remove lockdown",
                ]
            },
            "❌ Emergency": {
                "description": "Manual emergency controls for admins during an active attack.",
                "commands": [
                    "`/antinuke emergency lock` — Lock all channels",
                    "`/antinuke emergency unlock` — Unlock all channels",
                    "`/antinuke emergency kick_nuker` — Kick a specific nuker",
                ]
            },
            "🔧 Moderation": {
                "description": "Ban, kick, mute, warn, purge and more.",
                "commands": [
                    "`/ban` — Ban a member",
                    "`/kick` — Kick a member",
                    "`/mute` — Timeout a member",
                    "`/warn` — Warn a member",
                    "`/purge` — Delete messages",
                ]
            },
            "🔧 Utility": {
                "description": "Useful information commands — avatar, ping, server info.",
                "commands": [
                    "`/avatar` — Show a user's avatar",
                    "`/userinfo` — View user details",
                    "`/serverinfo` — Server information",
                    "`/ping` — Bot latency",
                ]
            },
            "🔨 Automod": {
                "description": "Spam detection, invite blocking, bad word filter.",
                "commands": [
                    "`/automod spam_on` — Enable spam detection",
                    "`/automod invites_on` — Block invite links",
                    "`/automod words_add` — Add filtered word",
                ]
            },
            "📬 Welcoming": {
                "description": "Custom welcome/farewell messages & auto‑role.",
                "commands": [
                    "`/welcome channel` — Set welcome channel",
                    "`/welcome message` — Custom welcome text",
                    "`/welcome role` — Auto‑assign role on join",
                    "`/farewell channel` — Set farewell channel",
                ]
            },
            "🔷 Customroles": {
                "description": "Let members create and manage their own custom roles.",
                "commands": [
                    "`/customrole create` — Create a personal role",
                    "`/customrole delete` — Delete your role",
                    "`/customrole list` — List your roles",
                ]
            },
            "☄️ Giveaway": {
                "description": "Button‑based giveaways with rerolls & role requirements.",
                "commands": [
                    "`/gstart` — Start a giveaway",
                    "`/gend` — End a giveaway early",
                    "`/greroll` — Reroll winners",
                ]
            },
            "🔷 Boycott/VcBan": {
                "description": "Voice channel bans and server boycotts.",
                "commands": [
                    "`/vcban` — Ban user from all voice channels",
                    "`/unvcban` — Remove voice ban",
                    "`/boycott` — Ban user from the server permanently",
                ]
            },
            "✅ Automations": {
                "description": "Scheduled messages & auto tasks.",
                "commands": [
                    "`/auto message_add` — Schedule a recurring message",
                    "`/auto message_remove` — Remove last scheduled message",
                ]
            },
            "👤 Fun": {
                "description": "Memes, 8ball, rock‑paper‑scissors.",
                "commands": [
                    "`/8ball` — Ask the magic 8ball",
                    "`/meme` — Random meme",
                    "`/rps` — Rock‑paper‑scissors",
                ]
            },
            "🎙️ Voice": {
                "description": "Voice channel management & stats.",
                "commands": [
                    "`/voicestats` — Voice activity info",
                    "`/vc kick` — Kick from voice",
                    "`/vc mute` — Mute in voice",
                ]
            },
            "⚙️ Admin / Mod Setup": {
                "description": "Create staff roles with pre‑configured permissions.",
                "commands": [
                    "`/setup admin.exe` — Create admin role",
                    "`/setup nuke.exe` — Create nuke role",
                    "`/roleassign` — Assign roles to members",
                ]
            },
            "⚙️ Ignore Commands": {
                "description": "Make the bot ignore specific users or channels.",
                "commands": [
                    "`/ignore user` — Ignore a user",
                    "`/ignore channel` — Ignore a channel",
                    "`/unignore` — Remove ignore",
                ]
            },
        }

        # Dropdown options (skip Home)
        self.dropdown_options = []
        for idx, module in enumerate(self.modules[1:]):
            emoji = module.split()[0]
            name = " ".join(module.split()[1:])
            self.dropdown_options.append(
                discord.SelectOption(
                    label=name,
                    description=self.module_data[module]["description"][:50],
                    value=str(idx + 1),
                    emoji=emoji
                )
            )

        self.select_menu = Select(
            placeholder="Navigate to a category",
            options=self.dropdown_options,
            custom_id="help_select"
        )
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

        self.add_item(NavButton("◀◀", "first", discord.ButtonStyle.secondary, 1))
        self.add_item(NavButton("◀", "prev", discord.ButtonStyle.secondary, 1))
        self.add_item(NavButton("✕", "close", discord.ButtonStyle.danger, 1))
        self.add_item(NavButton("▶", "next", discord.ButtonStyle.secondary, 1))
        self.add_item(NavButton("▶▶", "last", discord.ButtonStyle.secondary, 1))

    def build_embed(self):
        module_name = self.modules[self.current_page]
        data = self.module_data[module_name]

        embed = discord.Embed(
            title="NeoMonster",
            description=data["description"],
            color=BLUE_MAIN,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        if self.current_page == 0:  # Home
            embed.add_field(
                name="Overview",
                value=(
                    "**Prefix:** `/`\n"
                    "**Total Commands:** `65+`\n"
                    "**Website:** [neomonster.bot](https://neomonster1-production.up.railway.app)\n"
                    "**Support:** [Join Server](https://discord.gg/f8zTc4tmHx)"
                ),
                inline=False,
            )
            embed.add_field(
                name="Quick Guide",
                value=(
                    "Use `/help <command>` to get details on a specific command.\n"
                    "Example: `/help mute`\n\n"
                    "Select a category from the dropdown below to browse available commands."
                ),
                inline=False,
            )
            # Short category list — names only, no descriptions (fits in 1024 chars)
            cat_lines = []
            for mod in self.modules[1:]:
                emoji = mod.split()[0]
                name = " ".join(mod.split()[1:])
                if name == "Boycott/VcBan":
                    cat_lines.append(f"{emoji} **{name}** `NEW`")
                else:
                    cat_lines.append(f"{emoji} **{name}**")
            embed.add_field(name="Categories", value="\n".join(cat_lines), inline=False)

        else:  # Category page
            cmds = data.get("commands", [])
            if cmds:
                embed.add_field(name="Commands", value="\n".join(cmds), inline=False)
            else:
                embed.add_field(name="Commands", value="No commands available.", inline=False)

        embed.set_footer(
            text=f"Page {self.current_page+1} of {len(self.modules)} • NeoMonster Security"
        )
        return embed

    async def select_callback(self, interaction: discord.Interaction):
        idx = int(self.select_menu.values[0])
        self.current_page = idx
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def button_callback(self, interaction: discord.Interaction, action: str):
        if action == "first":
            self.current_page = 0
        elif action == "prev":
            self.current_page = max(0, self.current_page - 1)
        elif action == "next":
            self.current_page = min(len(self.modules) - 1, self.current_page + 1)
        elif action == "last":
            self.current_page = len(self.modules) - 1
        elif action == "close":
            await interaction.message.delete()
            self.stop()
            return
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)


class NavButton(Button):
    def __init__(self, label, action, style, row):
        super().__init__(label=label, style=style, row=row)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        await view.button_callback(interaction, self.action)


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Browse all commands and modules")
    async def help_command(self, interaction: discord.Interaction):
        view = HelpView(self.bot)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(HelpCog(bot))