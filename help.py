import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select

BLUE_MAIN = 0x3B82F6

class HelpView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=120)
        self.bot = bot
        self.current_page = 0
        self.message = None

        # ---------- YOUR CUSTOM EMOJI CODES ----------
        self.emoji_antinuke   = "<:sheild:1532827229149724835>"
        self.emoji_betray     = "<:lock:1532827337832398969>"
        self.emoji_limit      = "<:Limit:1532827385441943552>"
        self.emoji_auto_emerg = "<:sword:1532827462998687815>"
        self.emoji_emergency  = "<:sword2:1532827540081741964>"
        self.emoji_moderation = "<:hammer_wrench:1532828069113626755>"
        self.emoji_utility    = "<:wrenchs:1532827639696461935>"
        self.emoji_automod    = "<:admin_modsetup:1532828408692740156>"
        self.emoji_welcoming  = "<:welcome:1532827778217672785>"
        self.emoji_customroles= "<:start2:1532827987802722395>"
        self.emoji_giveaway   = "<:party:1532827934698508519>"
        self.emoji_boycott    = "<:star:1532827870337175746>"
        self.emoji_automations= "<:double_check:1532828586317316226>"
        self.emoji_fun        = "<:fun:1532828529035710674>"
        self.emoji_voice      = "<:microphone:1532828487579336714>"
        self.emoji_admin      = "⚙️"
        self.emoji_ignore     = "⚙️"
        # ------------------------------------------------------------------------

        self.modules = [
            ("🏠 Home", None),
            (f"{self.emoji_antinuke} Antinuke Security", "Antinuke Security"),
            (f"{self.emoji_betray} Anti Betray", "Anti Betray"),
            (f"{self.emoji_limit} Limit System", "Limit System"),
            (f"{self.emoji_auto_emerg} Auto Emergency", "Auto Emergency"),
            (f"{self.emoji_emergency} Emergency", "Emergency"),
            (f"{self.emoji_moderation} Moderation", "Moderation"),
            (f"{self.emoji_utility} Utility", "Utility"),
            (f"{self.emoji_automod} Automod", "Automod"),
            (f"{self.emoji_welcoming} Welcoming", "Welcoming"),
            (f"{self.emoji_customroles} Customroles", "Customroles"),
            (f"{self.emoji_giveaway} Giveaway", "Giveaway"),
            (f"{self.emoji_boycott} Boycott/VcBan", "Boycott/VcBan"),
            (f"{self.emoji_automations} Automations", "Automations"),
            (f"{self.emoji_fun} Fun", "Fun"),
            (f"{self.emoji_voice} Voice", "Voice"),
            (f"{self.emoji_admin} Admin / Mod Setup", "Admin / Mod Setup"),
            (f"{self.emoji_ignore} Ignore Commands", "Ignore Commands"),
            # 🆕 New modules
            ("🎟️ Tickets", "Tickets"),
            ("📊 Polls", "Polls"),
            ("📋 Logging", "Logging"),
        ]

        self.module_data = {
            "Antinuke Security": {
                "description": "Anti‑nuke, anti‑spam, lockdown & raid protection.",
                "commands": [
                    "`/antinuke settings` — View current security config",
                    "`/antinuke toggle` — Enable/disable anti‑nuke",
                    "`/antinuke emergency` — Lockdown or kick nukers",
                    "`/massmention` — Manage mass‑mention protection",
                    "`/antivanity` — Block custom invite links",
                ]
            },
            "Anti Betray": {
                "description": "Prevents trusted members from abusing power and betraying the server.",
                "commands": [
                    "`/antinuke whitelist add` — Add trusted admins",
                    "`/antinuke emergency kick_nuker` — Remove a rogue admin",
                ]
            },
            "Limit System": {
                "description": "Rate‑limit destructive actions to prevent mass spam and floods.",
                "commands": [
                    "`/antinuke threshold` — Set action limits",
                    "`/antinuke timewindow` — Detection time window",
                ]
            },
            "Auto Emergency": {
                "description": "Automatically locks the server when a nuke is detected.",
                "commands": [
                    "`/antinuke emergency lock` — Manual lockdown",
                    "`/antinuke emergency unlock` — Remove lockdown",
                ]
            },
            "Emergency": {
                "description": "Manual emergency controls for admins during an active attack.",
                "commands": [
                    "`/antinuke emergency lock` — Lock all channels",
                    "`/antinuke emergency unlock` — Unlock all channels",
                    "`/antinuke emergency kick_nuker` — Kick a specific nuker",
                ]
            },
            "Moderation": {
                "description": "Ban, kick, mute, warn, purge and more.",
                "commands": [
                    "`/ban` — Ban a member",
                    "`/kick` — Kick a member",
                    "`/mute` — Timeout a member",
                    "`/unmute` — Remove timeout",
                    "`/warn` — Warn a member",
                    "`/purge` — Delete messages",
                ]
            },
            "Utility": {
                "description": "Useful information commands — avatar, ping, server info.",
                "commands": [
                    "`/avatar` — Show a user's avatar",
                    "`/userinfo` — View user details",
                    "`/serverinfo` — Server information",
                    "`/ping` — Bot latency",
                ]
            },
            "Automod": {
                "description": "Spam detection, invite blocking, bad word filter.",
                "commands": [
                    "`/automod spam_on` — Enable spam detection",
                    "`/automod invites_on` — Block invite links",
                    "`/automod words_add` — Add filtered word",
                ]
            },
            "Welcoming": {
                "description": "Custom welcome/farewell messages & auto‑role.",
                "commands": [
                    "`/welcome channel` — Set welcome channel",
                    "`/welcome message` — Custom welcome text",
                    "`/welcome role` — Auto‑assign role on join",
                    "`/farewell channel` — Set farewell channel",
                ]
            },
            "Customroles": {
                "description": "Let members create and manage their own custom roles.",
                "commands": [
                    "`/customrole create` — Create a personal role",
                    "`/customrole delete` — Delete your role",
                    "`/customrole list` — List your roles",
                ]
            },
            "Giveaway": {
                "description": "Button‑based giveaways with rerolls & role requirements.",
                "commands": [
                    "`/gstart` — Start a giveaway",
                    "`/gend` — End a giveaway early",
                    "`/greroll` — Reroll winners",
                ]
            },
            "Boycott/VcBan": {
                "description": "Voice channel bans and server boycotts.",
                "commands": [
                    "`/vcban` — Ban user from all voice channels",
                    "`/unvcban` — Remove voice ban",
                    "`/boycott` — Ban user from the server permanently",
                ]
            },
            "Automations": {
                "description": "Scheduled messages & auto tasks.",
                "commands": [
                    "`/auto message_add` — Schedule a recurring message",
                    "`/auto message_remove` — Remove last scheduled message",
                ]
            },
            "Fun": {
                "description": "Memes, 8ball, rock‑paper‑scissors.",
                "commands": [
                    "`/8ball` — Ask the magic 8ball",
                    "`/meme` — Random meme",
                    "`/rps` — Rock‑paper‑scissors",
                ]
            },
            "Voice": {
                "description": "Voice channel management & stats.",
                "commands": [
                    "`/voicestats` — Voice activity info",
                    "`/vc kick` — Kick from voice",
                    "`/vc mute` — Mute in voice",
                ]
            },
            "Admin / Mod Setup": {
                "description": "Create staff roles with pre‑configured permissions.",
                "commands": [
                    "`/setup admin.exe` — Create admin role",
                    "`/setup nuke.exe` — Create nuke role",
                    "`/roleassign` — Assign roles to members",
                ]
            },
            "Ignore Commands": {
                "description": "Make the bot ignore specific users or channels.",
                "commands": [
                    "`/ignore user` — Ignore a user",
                    "`/ignore channel` — Ignore a channel",
                    "`/unignore` — Remove ignore",
                ]
            },
            # 🆕 New module data
            "Tickets": {
                "description": "Professional ticket system with support, reward, report types.",
                "commands": [
                    "`/ticket` — Open a ticket (Support, Reward, Report, Other)",
                    "`/ticketsetup` — Configure ticket types and support roles",
                    "`/ticket-add` — Add a user to the ticket",
                    "`/ticket-remove` — Remove a user from the ticket",
                    "`/ticket-rename` — Rename the ticket channel",
                    "`/ticket-close` — Close and delete the ticket",
                    "`/ticket-claim` — Claim the ticket for yourself",
                ]
            },
            "Polls": {
                "description": "Create interactive polls with up to 10 options.",
                "commands": [
                    "`/poll` — Create a poll (modal for options)",
                    "Vote by clicking the buttons below the poll!",
                ]
            },
            "Logging": {
                "description": "Full server logging: messages, voice, members, channels, roles, etc.",
                "commands": [
                    "`/logchannel` — Set a log channel for any event type",
                    "Event types: `message`, `voice`, `member`, `server`, `channel`, `role`, `emoji`, `webhook`, `moderation`",
                    "`/messagelog` — Quick setup for message edit/delete logs",
                    "`/stafflog` — View staff activity (moderation actions)",
                ]
            },
        }

        # Dropdown options (skip Home)
        self.dropdown_options = []
        for idx, (full, name) in enumerate(self.modules[1:]):
            emoji_str = full.split()[0]
            self.dropdown_options.append(
                discord.SelectOption(
                    label=name,
                    description=self.module_data[name]["description"][:50],
                    value=str(idx + 1),
                    emoji=emoji_str
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
        if self.current_page == 0:
            embed = discord.Embed(
                title="NeoMonster",
                description="Advanced server security, automated moderation, and seamless community management — all in one powerful bot.",
                color=BLUE_MAIN,
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
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
            cat_lines = []
            for full, name in self.modules[1:]:
                emoji = full.split()[0]
                display = f"{emoji} : **{name}**"
                if name == "Boycott/VcBan":
                    display += " `NEW`"
                cat_lines.append(display)
            embed.add_field(name="Categories", value="\n".join(cat_lines), inline=False)
            embed.set_footer(text=f"Page 1 of {len(self.modules)} • NeoMonster Security")
            return embed

        full, name = self.modules[self.current_page]
        data = self.module_data[name]
        embed = discord.Embed(title="NeoMonster", description=data["description"], color=BLUE_MAIN)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        cmds = data.get("commands", [])
        embed.add_field(name="Commands", value="\n".join(cmds) if cmds else "No commands available.", inline=False)
        embed.set_footer(text=f"Page {self.current_page+1} of {len(self.modules)} • NeoMonster Security")
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