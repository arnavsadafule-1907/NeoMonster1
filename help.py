import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from importlib import import_module

try:
    get_emoji = import_module("utils.emoji_manager").get_emoji
except (ImportError, AttributeError):
    _EMOJI_FALLBACKS = {
        "shield": "🛡️", "lock": "🔒", "firewall": "🔥", "warning": "⚠️",
        "moderation": "🔨", "tools": "🛠️", "slowmode": "🐢", "wave": "👋",
        "sparkles": "✨", "giveaway": "🎉", "ban": "🚫", "double_check": "✅",
        "dice": "🎲", "microphone": "🎙️", "crown": "👑", "settings": "⚙️",
        "ticket": "🎫", "logs": "📜", "guide": "📖", "staff": "👥",
        "dm": "💬", "pin": "📌", "server": "🌐", "game": "🎮", "stats": "📊",
    }

    def get_emoji(name):
        return _EMOJI_FALLBACKS.get(name, "")

BLUE_MAIN = 0x3B82F6


class HelpView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=120)
        self.bot = bot
        self.current_page = 0
        self.message = None

        self.emoji_antinuke    = get_emoji("shield")
        self.emoji_betray      = get_emoji("lock")
        self.emoji_limit       = get_emoji("firewall")
        self.emoji_auto_emerg  = get_emoji("shield")
        self.emoji_emergency   = get_emoji("warning")
        self.emoji_moderation  = get_emoji("moderation")
        self.emoji_utility     = get_emoji("tools")
        self.emoji_automod     = get_emoji("slowmode")
        self.emoji_welcoming   = get_emoji("wave")
        self.emoji_customroles = get_emoji("sparkles")
        self.emoji_giveaway    = get_emoji("giveaway")
        self.emoji_boycott     = get_emoji("ban")
        self.emoji_automations = get_emoji("double_check")
        self.emoji_fun         = get_emoji("dice")
        self.emoji_voice       = get_emoji("microphone")
        self.emoji_admin       = get_emoji("crown")
        self.emoji_ignore      = get_emoji("settings")
        self.emoji_tickets     = get_emoji("ticket")
        self.emoji_logging     = get_emoji("logs")
        self.emoji_guide       = get_emoji("guide")
        self.emoji_staff       = get_emoji("staff")
        self.emoji_owner       = get_emoji("crown")
        self.emoji_dm          = get_emoji("dm")
        self.emoji_sticky      = get_emoji("pin")
        self.emoji_server      = get_emoji("server")
        self.emoji_mc          = get_emoji("game")
        self.emoji_stats       = get_emoji("stats")

        # ✅ KEEP THIS UNDER 25 (Discord Select menu hard limit)
        self.modules = [
            ("🏠 Home", None),
            (f"{self.emoji_antinuke} Antinuke Security", "Antinuke Security"),
            (f"{self.emoji_moderation} Moderation", "Moderation"),
            (f"{self.emoji_utility} Utility", "Utility"),
            (f"{self.emoji_welcoming} Welcoming", "Welcoming"),
            (f"{self.emoji_customroles} Customroles", "Customroles"),
            (f"{self.emoji_giveaway} Giveaway", "Giveaway"),
            (f"{self.emoji_boycott} Boycott/VcBan", "Boycott/VcBan"),
            (f"{self.emoji_automations} Automations", "Automations"),
            (f"{self.emoji_fun} Fun", "Fun"),
            (f"{self.emoji_voice} Voice", "Voice"),
            (f"{self.emoji_admin} Admin / Mod Setup", "Admin / Mod Setup"),
            (f"{self.emoji_ignore} Ignore Commands", "Ignore Commands"),
            (f"{self.emoji_tickets} Tickets", "Tickets"),
            (f"{self.emoji_logging} Logging", "Logging"),
            (f"{self.emoji_guide} Setup Guide", "Setup Guide"),
            (f"{self.emoji_staff} Staff System", "Staff System"),
            (f"{self.emoji_owner} Owner Tools", "Owner Tools"),
            (f"{self.emoji_dm} DM Management", "DM Management"),
            (f"{self.emoji_sticky} Sticky Messages", "Sticky Messages"),
            (f"{self.emoji_server} Server Status", "Server Status"),
            (f"{self.emoji_mc} Minecraft Status", "Minecraft Status"),
            (f"{self.emoji_stats} Stats & Tracking", "Stats & Tracking"),
        ]

        self.module_data = {
            "Antinuke Security": {
                "description": "Anti-nuke, anti-spam, lockdown & raid protection. (admin.exe / nuke.exe)",
                "commands": [
                    "**🛡️ Anti-Nuke**",
                    "`/antinuke settings` — View current security config",
                    "`/antinuke toggle` — Enable/disable anti-nuke",
                    "`/antinuke emergency` — Lockdown or kick nukers",
                    "`/massmention` — Manage mass-mention protection",
                    "`/antivanity` — Block custom invite links",
                    "",
                    "**🕵️ Anti Betray**",
                    "`/antinuke whitelist add` — Add trusted admins",
                    "`/antinuke emergency kick_nuker` — Remove a rogue admin",
                    "",
                    "**⏱️ Limit System**",
                    "`/antinuke threshold` — Set action limits",
                    "`/antinuke timewindow` — Detection time window",
                    "",
                    "**🚨 Auto Emergency**",
                    "`/antinuke emergency lock` — Manual lockdown",
                    "`/antinuke emergency unlock` — Remove lockdown",
                    "",
                    "**⚔️ Emergency Controls**",
                    "`/antinuke emergency lock` — Lock all channels",
                    "`/antinuke emergency unlock` — Unlock all channels",
                    "`/antinuke emergency kick_nuker` — Kick a specific nuker",
                ]
            },
            "Moderation": {
                "description": "Ban, kick, mute, warn, purge and more. Requires Staff.exe or higher.",
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
                "description": "Useful information commands — avatar, ping, server info. (Anyone can use)",
                "commands": [
                    "`/avatar` — Show a user's avatar",
                    "`/userinfo` — View user details",
                    "`/serverinfo` — Server information",
                    "`/ping` — Bot latency",
                ]
            },
            "Welcoming": {
                "description": "Custom welcome/farewell messages & auto-role. (admin.exe / nuke.exe)",
                "commands": [
                    "`/welcome channel` — Set welcome channel",
                    "`/welcome message` — Custom welcome text",
                    "`/welcome role` — Auto-assign role on join",
                    "`/farewell channel` — Set farewell channel",
                ]
            },
            "Customroles": {
                "description": "Let members create and manage their own custom roles. (admin.exe / nuke.exe)",
                "commands": [
                    "`/customrole create` — Create a personal role",
                    "`/customrole delete` — Delete your role",
                    "`/customrole list` — List your roles",
                ]
            },
            "Giveaway": {
                "description": "Button-based giveaways with rerolls & role requirements. (nuke.exe only)",
                "commands": [
                    "`/gstart` — Start a giveaway",
                    "`/gend` — End a giveaway early",
                    "`/greroll` — Reroll winners",
                ]
            },
            "Boycott/VcBan": {
                "description": "Voice channel bans and server boycotts. (admin.exe / nuke.exe)",
                "commands": [
                    "`/vcban` — Ban user from all voice channels",
                    "`/unvcban` — Remove voice ban",
                    "`/boycott` — Ban user from the server permanently",
                ]
            },
            "Automations": {
                "description": "Scheduled messages & auto tasks. (admin.exe / nuke.exe)",
                "commands": [
                    "`/auto message_add` — Schedule a recurring message",
                    "`/auto message_remove` — Remove last scheduled message",
                ]
            },
            "Fun": {
                "description": "Memes, 8ball, rock-paper-scissors. (Anyone can use)",
                "commands": [
                    "`/8ball` — Ask the magic 8ball",
                    "`/meme` — Random meme",
                    "`/rps` — Rock-paper-scissors",
                ]
            },
            "Voice": {
                "description": "Voice channel management & stats. (admin.exe / nuke.exe)",
                "commands": [
                    "`/voicestats` — Voice activity info",
                    "`/vc kick` — Kick from voice",
                    "`/vc mute` — Mute in voice",
                    "`/vc unmute` — Unmute in voice",
                ]
            },
            "Admin / Mod Setup": {
                "description": "Create staff roles with pre-configured permissions.",
                "commands": [
                    "`/setup admin.exe` — Create admin role",
                    "`/setup nuke.exe` — Create nuke role",
                    "`/setup staff.exe` — Create staff role (moderation, polls, announce)",
                    "`/setup ticketsupporter` — Create ticket helper role",
                    "`/assign` — Assign any of the four roles to a member (server owner / extra owners only)",
                ]
            },
            "Ignore Commands": {
                "description": "Make the bot ignore specific users or channels. (admin.exe / nuke.exe)",
                "commands": [
                    "`/ignore user` — Ignore a user",
                    "`/ignore channel` — Ignore a channel",
                    "`/unignore` — Remove ignore",
                ]
            },
            "Tickets": {
                "description": "Persistent ticket panel with custom types & welcome messages.",
                "commands": [
                    "`/ticketpanel send` — Send the ticket panel (admin only)",
                    "`/ticketpanel edit` — Customise panel title, description, image, style",
                    "`/ticketpanel reset` — Reset panel to defaults (admin only)",
                    "`/tickettype add` — Add a custom ticket type (admin only)",
                    "`/tickettype remove` — Remove a ticket type (admin only)",
                    "`/ticket_add` — Add a user to the current ticket",
                    "`/ticket_remove` — Remove a user from the current ticket",
                    "`/ticket_rename` — Rename the current ticket",
                    "`/ticket_close` — Close the current ticket",
                    "`/ticket_claim` — Claim the current ticket",
                ]
            },
            "Logging": {
                "description": "Full server logging: messages, voice, members, channels, roles, etc.",
                "commands": [
                    "`/setlog` — Set a log channel for any event type (Staff.exe+)",
                    "`/stafflog` — View staff activity",
                ]
            },
            "Setup Guide": {
                "description": "Everything you need to know to configure roles and permissions.",
                "commands": [
                    "**🔰 Role Overview**",
                    "• `nuke.exe` – Full server owner access.",
                    "• `admin.exe` – Anti-nuke, automod, server settings.",
                    "• `Staff.exe` – Moderation, polls, announce, logs.",
                    "• `TicketSupporter` – Manage tickets.",
                    "",
                    "**⚡ How to create a role**",
                    "1. Run `/setup <role>`.",
                    "2. The bot creates the role with correct permissions.",
                    "3. Use `/assign` to give the role to a member.",
                ]
            },
            "Staff System": {
                "description": "Ticket statistics, leaderboard, leave system, and staff activity logs.",
                "commands": [
                    "**📊 Staff Stats**",
                    "`/staffstats @user` — Show tickets claimed, closed, leave days",
                    "`/staffleaderboard` — View the staff leaderboard",
                    "`/stafflog @user` — View a staff member's moderation log",
                    "",
                    "**🏖️ Leave System**",
                    "`/leavepanel send` — Send the persistent leave panel",
                    "`/leavesetup @role` — Set the 'On Leave' role",
                    "`/leave` — Request leave or end leave early",
                ]
            },
            "Owner Tools": {
                "description": "Commands for the server owner and extra owners.",
                "commands": [
                    "`/addowner @user` — Promote a user to extra owner",
                    "`/removeowner @user` — Demote an extra owner",
                    "`/listowners` — Show all extra owners",
                    "`/dmall` — Send an embed to every server member via DM",
                    "`/cleanuptickets` — Delete orphaned ticket channels",
                    "`/closealltickets` — Close ALL active tickets",
                    "`/sync` — Force sync all slash commands",
                ]
            },
            "DM Management": {
                "description": "Send bulk DMs to your server members with full tracking and control.",
                "commands": [
                    "`/dmall` — Send an embed to every member",
                    "`/dmstatus` — Show the status of the current campaign",
                    "`/dmcancel` — Cancel the currently running campaign",
                ]
            },
            "Sticky Messages": {
                "description": "Pin an auto-reposting message at the bottom of a channel.",
                "commands": [
                    "`/stick <content>` — Set a sticky message in the current channel",
                    "`/stickstop` — Disable the sticky message",
                    "`/stickremove` — Remove the sticky message",
                    "`/sticklist` — List all sticky messages",
                ]
            },
            "Server Status": {
                "description": "Live Discord bot status and current server information.",
                "commands": [
                    "`/serverstatus` — Show bot uptime, ping, memory, and Discord server stats.",
                ]
            },
            "Minecraft Status": {
                "description": "Check Minecraft server status — one-time or live.",
                "commands": [
                    "`/mcstatus <address> [edition]` — One-time status snapshot.",
                    "`/mclive <address> [edition]` — Start a live panel (updates every 60s).",
                    "`/mclive` — Stop the live panel in this channel.",
                ]
            },
            "Stats & Tracking": {
                "description": "Track invites and messages with leaderboards and staff management.",
                "commands": [
                    "**📨 Invite Tracking**",
                    "`/invites [user]` — Show invite stats for a user.",
                    "`/invited [user]` — Show who invited a user.",
                    "`/inviteleaderboard` — Top inviters in this server.",
                    "",
                    "**💬 Message Tracking**",
                    "`/messages [user]` — Show message stats for a user.",
                    "`/msgleaderboard` — Top message senders in this server.",
                    "",
                    "**🛠️ Staff**",
                    "`/managetracking` — Adjust invite/message stats for a user.",
                ]
            },
        }

        # ---------- Build dropdown options ----------
        # ⚠️ Discord API REJECTS custom/application emojis in SelectOption.emoji
        # Only unicode emojis and guild emojis are allowed here.
        # Custom emojis still work in embeds, buttons, and page content.
        _dropdown_unicode = {
            "Antinuke Security": "🛡️",
            "Moderation": "🔨",
            "Utility": "🛠️",
            "Welcoming": "👋",
            "Customroles": "✨",
            "Giveaway": "🎉",
            "Boycott/VcBan": "🚫",
            "Automations": "✅",
            "Fun": "🎲",
            "Voice": "🎙️",
            "Admin / Mod Setup": "👑",
            "Ignore Commands": "⚙️",
            "Tickets": "🎫",
            "Logging": "📜",
            "Setup Guide": "📖",
            "Staff System": "👥",
            "Owner Tools": "👑",
            "DM Management": "💬",
            "Sticky Messages": "📌",
            "Server Status": "🌐",
            "Minecraft Status": "🎮",
            "Stats & Tracking": "📊",
        }

        self.dropdown_options = []
        for idx, (full, name) in enumerate(self.modules[1:]):
            option_kwargs = {
                "label": name,
                "description": self.module_data[name]["description"][:100],
                "value": str(idx + 1),
            }
            unicode_emoji = _dropdown_unicode.get(name)
            if unicode_emoji:
                option_kwargs["emoji"] = unicode_emoji
            self.dropdown_options.append(discord.SelectOption(**option_kwargs))

        if len(self.dropdown_options) > 25:
            self.dropdown_options = self.dropdown_options[:25]

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

    @staticmethod
    def _split_commands(cmd_list, max_len=1024):
        fields = []
        current = ""
        for line in cmd_list:
            if len(current) + len(line) + 1 > max_len:
                fields.append(current.strip())
                current = line
            else:
                if current:
                    current += "\n"
                current += line
        if current:
            fields.append(current.strip())
        return fields

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
                    "**Total Commands:** `95+`\n"
                    "**Website:** [NeoMonster.bot](https://neomonster1.onrender.com)\n"
                    "**Support:** [Join Server](https://discord.gg/f8zTc4tmHx)"
                ),
                inline=False,
            )
            embed.add_field(
                name="Quick Guide",
                value=(
                    "Use `/help <command>` to get details on a specific command.\n"
                    "Example: `/help mute`\n\n"
                    "Select a category from the dropdown below to browse available commands.\n"
                    "👉 Check the **Setup Guide** for role configuration and permissions."
                ),
                inline=False,
            )
            cat_lines = []
            for full, name in self.modules[1:]:
                emoji = full.split()[0]
                display = f"{emoji} : **{name}**"
                if name in ("DM Management", "Sticky Messages", "Minecraft Status", "Stats & Tracking"):
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
        if cmds:
            chunks = self._split_commands(cmds)
            for idx, chunk in enumerate(chunks):
                field_name = "Commands" if idx == 0 else f"Commands (cont. {idx+1})"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="Commands", value="No commands available.", inline=False)
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
        try:
            view = HelpView(self.bot)
            embed = view.build_embed()
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"❌ Help failed: `{e}`", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Help failed: `{e}`", ephemeral=True)
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(HelpCog(bot))