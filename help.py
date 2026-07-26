import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select

BLUE_MAIN = 0x3B82F6
BLUE_ACCENT = 0x60A5FA

class HelpView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=60)  # auto‑disable after 60 seconds
        self.bot = bot
        self.current_page = 0
        self.message = None

        # Modules list (Home + all categories)
        self.modules = [
            "🏠 Home",
            "🛡️ Security",
            "🔨 Moderation",
            "⚙️ Administration",
            "🎉 Giveaways",
            "🤖 Utility",
            "👋 Welcoming",
            "📊 Logging",
            "💬 Tickets",
            "🎮 Fun",
            "🎤 Voice",
            "⚡ Automations",
        ]

        # Data for each module
        self.module_data = {
            "🏠 Home": {
                "description": "Welcome to NeoMonster – your ultimate Discord security and community bot!",
                "commands": []
            },
            "🛡️ Security": {
                "description": "Anti‑nuke, anti‑spam, lockdown & raid protection.",
                "commands": [
                    "`/antinuke settings` – View current security config",
                    "`/antinuke toggle` – Enable/disable anti‑nuke",
                    "`/antinuke emergency` – Lockdown or kick nukers",
                    "`/massmention` – Manage mass mention protection",
                    "`/antivanity` – Block vanity invite links",
                ]
            },
            "🔨 Moderation": {
                "description": "Ban, kick, mute, warn, purge and more.",
                "commands": [
                    "`/ban` – Ban a member",
                    "`/kick` – Kick a member",
                    "`/mute` – Timeout a member",
                    "`/warn` – Warn a member",
                    "`/purge` – Delete messages",
                ]
            },
            "⚙️ Administration": {
                "description": "Staff setup, role assignment & server management.",
                "commands": [
                    "`/setup` – Create admin/nuke roles",
                    "`/roleassign` – Assign staff roles",
                    "`/backup` – Create a server backup",
                    "`/restore` – Restore from backup",
                ]
            },
            "🎉 Giveaways": {
                "description": "Button‑based giveaways with rerolls & role requirements.",
                "commands": [
                    "`/gstart` – Start a giveaway",
                    "`/gend` – End a giveaway early",
                    "`/greroll` – Reroll winners",
                ]
            },
            "🤖 Utility": {
                "description": "Useful info commands like avatar, ping, serverinfo.",
                "commands": [
                    "`/avatar` – Show a user's avatar",
                    "`/userinfo` – View user details",
                    "`/serverinfo` – Server information",
                    "`/ping` – Bot latency",
                ]
            },
            "👋 Welcoming": {
                "description": "Custom welcome/farewell messages & auto‑role.",
                "commands": [
                    "`/welcome` – Configure welcome settings",
                    "`/farewell` – Set farewell channel",
                ]
            },
            "📊 Logging": {
                "description": "Message logs, staff activity tracker.",
                "commands": [
                    "`/messagelog` – Set message log channel",
                    "`/stafflog` – View staff activity",
                ]
            },
            "💬 Tickets": {
                "description": "Coming soon – private support tickets.",
                "commands": []
            },
            "🎮 Fun": {
                "description": "Memes, 8ball, rock‑paper‑scissors.",
                "commands": [
                    "`/8ball` – Ask the magic 8ball",
                    "`/meme` – Random meme",
                    "`/rps` – Rock‑paper‑scissors",
                ]
            },
            "🎤 Voice": {
                "description": "Voice channel management & stats.",
                "commands": [
                    "`/voicestats` – Voice activity info",
                    "`/vc` – Voice kick/mute",
                ]
            },
            "⚡ Automations": {
                "description": "Scheduled messages & auto tasks.",
                "commands": [
                    "`/auto` – Schedule a message",
                ]
            },
        }

        # Dropdown options (skip Home)
        self.dropdown_options = []
        for idx, module in enumerate(self.modules[1:]):
            emoji = module.split()[0]
            self.dropdown_options.append(
                discord.SelectOption(
                    label=module.split(maxsplit=1)[1],
                    description=self.module_data[module]["description"][:50],
                    value=str(idx + 1),
                    emoji=emoji
                )
            )

        self.select_menu = Select(
            placeholder="Choose a Module",
            options=self.dropdown_options,
            custom_id="help_select"
        )
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

        # Navigation buttons
        self.add_item(NavButton("◀ First", "first", discord.ButtonStyle.secondary, 1))
        self.add_item(NavButton("⬅ Previous", "prev", discord.ButtonStyle.secondary, 1))
        self.add_item(NavButton("❌ Close", "close", discord.ButtonStyle.danger, 1))
        self.add_item(NavButton("➡ Next", "next", discord.ButtonStyle.secondary, 1))
        self.add_item(NavButton("▶ Last", "last", discord.ButtonStyle.secondary, 1))

    def build_embed(self):
        module_name = self.modules[self.current_page]
        data = self.module_data[module_name]

        embed = discord.Embed(
            title="🤖 NeoMonster",
            description=data["description"],
            color=BLUE_MAIN,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        if self.current_page == 0:  # Home page
            embed.add_field(
                name="🤖 Bot Overview",
                value=(
                    "**Server Prefix:** `/`\n"
                    "**Total Commands:** `65+`\n"
                    "🌐 [Website](http://localhost:5000)\n"
                    "📧 coming soon"
                ),
                inline=False,
            )
            embed.add_field(
                name="❓ Quick Help",
                value="```\n/help <command>\n/help moderation\n/help giveaway\n/help security\n```",
                inline=False,
            )
            # Categories list
            cat_lines = []
            for mod in self.modules[1:]:
                emoji = mod.split()[0]
                name = mod.split(maxsplit=1)[1]
                desc = self.module_data[mod]["description"]
                cat_lines.append(f"{emoji} **{name}** – {desc}")
            embed.add_field(name="📂 Main Categories", value="\n".join(cat_lines), inline=False)

        else:  # Category page
            cmds = data.get("commands", [])
            if cmds:
                embed.add_field(
                    name="📋 Commands",
                    value="\n".join(cmds),
                    inline=False,
                )
            else:
                embed.add_field(name="📋 Commands", value="No commands available yet.", inline=False)

        embed.set_footer(
            text=f"NeoMonster • Page {self.current_page+1}/{len(self.modules)}",
            icon_url=self.bot.user.display_avatar.url
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

    @app_commands.command(name="help", description="Open the interactive help menu")
    async def help_command(self, interaction: discord.Interaction):
        view = HelpView(self.bot)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(HelpCog(bot))