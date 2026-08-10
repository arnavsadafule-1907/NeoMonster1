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
            ("🎟️ Tickets", "Tickets"),
            ("📊 Polls", "Polls"),
            ("📋 Logging", "Logging"),
            ("📖 Setup Guide", "Setup Guide"),
            ("📈 Staff Stats", "Staff Stats"),
            ("🏖️ Leave System", "Leave System"),
            ("👑 Owner Tools", "Owner Tools"),
        ]

        self.module_data = {
            "Antinuke Security": {
                "description": "Anti‑nuke, anti‑spam, lockdown & raid protection. (admin.exe / nuke.exe)",
                "commands": [
                    "`/antinuke settings` — View current security config",
                    "`/antinuke toggle` — Enable/disable anti‑nuke",
                    "`/antinuke emergency` — Lockdown or kick nukers",
                    "`/massmention` — Manage mass‑mention protection",
                    "`/antivanity` — Block custom invite links",
                ]
            },
            "Anti Betray": {
                "description": "Prevents trusted members from abusing power and betraying the server. (admin.exe / nuke.exe)",
                "commands": [
                    "`/antinuke whitelist add` — Add trusted admins",
                    "`/antinuke emergency kick_nuker` — Remove a rogue admin",
                ]
            },
            "Limit System": {
                "description": "Rate‑limit destructive actions to prevent mass spam and floods. (admin.exe / nuke.exe)",
                "commands": [
                    "`/antinuke threshold` — Set action limits",
                    "`/antinuke timewindow` — Detection time window",
                ]
            },
            "Auto Emergency": {
                "description": "Automatically locks the server when a nuke is detected. (admin.exe / nuke.exe)",
                "commands": [
                    "`/antinuke emergency lock` — Manual lockdown",
                    "`/antinuke emergency unlock` — Remove lockdown",
                ]
            },
            "Emergency": {
                "description": "Manual emergency controls for admins during an active attack. (admin.exe / nuke.exe)",
                "commands": [
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
            "Automod": {
                "description": "Spam detection, invite blocking, bad word filter. (admin.exe / nuke.exe)",
                "commands": [
                    "`/automod spam_on` — Enable spam detection",
                    "`/automod invites_on` — Block invite links",
                    "`/automod words_add` — Add filtered word",
                ]
            },
            "Welcoming": {
                "description": "Custom welcome/farewell messages & auto‑role. (admin.exe / nuke.exe)",
                "commands": [
                    "`/welcome channel` — Set welcome channel",
                    "`/welcome message` — Custom welcome text",
                    "`/welcome role` — Auto‑assign role on join",
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
                "description": "Button‑based giveaways with rerolls & role requirements. (nuke.exe only)",
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
                "description": "Memes, 8ball, rock‑paper‑scissors. (Anyone can use)",
                "commands": [
                    "`/8ball` — Ask the magic 8ball",
                    "`/meme` — Random meme",
                    "`/rps` — Rock‑paper‑scissors",
                ]
            },
            "Voice": {
                "description": "Voice channel management & stats. (admin.exe / nuke.exe)",
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
                    "`/ticketpanel` — Send the ticket panel dropdown (admin only)",
                    "`/tickettype add` — Add a custom ticket type (admin only)",
                    "`/tickettype remove` — Remove a ticket type (admin only)",
                    "`/ticket_add` — Add a user to the current ticket",
                    "`/ticket_remove` — Remove a user from the current ticket",
                    "`/ticket_rename` — Rename the current ticket",
                    "`/ticket_close` — Close the current ticket (prompts for reason)",
                    "`/ticket_claim` — Claim the current ticket",
                    "Use the dropdown on the panel to open a ticket.",
                    "Inside a ticket: Claim, Close, Add User, Remove User, Rename buttons.",
                    "Staff commands require TicketSupporter, Staff.exe, or higher.",
                ]
            },
            "Polls": {
                "description": "Create interactive polls with up to 10 options. Requires Staff.exe or higher.",
                "commands": [
                    "`/poll` — Create a poll (modal for options)",
                    "Vote by clicking the buttons below the poll!",
                ]
            },
            "Logging": {
                "description": "Full server logging: messages, voice, members, channels, roles, etc.",
                "commands": [
                    "`/setlog` — Set a log channel for any event type (Staff.exe+)",
                    "Event types: `message`, `voice`, `member`, `server`, `channel`, `role`, `emoji`, `webhook`, `moderation`",
                    "`/messagelog` — Quick setup for message edit/delete logs (Staff.exe+)",
                    "`/stafflog` — View staff activity (moderation actions)",
                ]
            },
            "Setup Guide": {
                "description": "Everything you need to know to configure roles and permissions.",
                "commands": [
                    "**🔰 Role Overview**",
                    "• `nuke.exe` – Full server owner access. Use `/setup nuke.exe` to create.",
                    "• `admin.exe` – Can manage anti‑nuke, automod, and server settings. Use `/setup admin.exe`.",
                    "• `Staff.exe` – Can moderate (ban, kick, mute), create polls, announce, and manage log channels. Use `/setup staff.exe`.",
                    "• `TicketSupporter` – Can manage tickets (claim, close, add users). Use `/setup ticketsupporter`.",
                    "",
                    "**⚡ How to create a role**",
                    "1. Run `/setup <role>` (e.g., `/setup admin.exe`).",
                    "2. The bot creates the role with the correct permissions.",
                    "3. Use `/assign` to give the role to a member.",
                    "",
                    "**🛡️ Who can use what?**",
                    "• Anyone: `/ping`, `/help`, fun commands, open tickets, vote in polls.",
                    "• TicketSupporter: Manage tickets (claim, close, add/remove users), use leave system.",
                    "• Staff.exe: All moderation commands, `/announce`, `/poll`, `/setlog`, `/slowmode`, `/messagelog`, `/staffstats`, `/leave`.",
                    "• admin.exe: Anti‑nuke config, automod, welcoming, custom roles, voice commands, backup/restore.",
                    "• nuke.exe: Giveaways, anti‑nuke emergency, whitelist, owner‑level bypass.",
                    "• Extra Owners: Have full owner‑level access (bypass all role checks).",
                    "",
                    "**👑 Owner Tools**",
                    "• `/addowner @user` — Promote a member to extra owner (server owner / bot owner only).",
                    "• `/removeowner @user` — Demote an extra owner.",
                    "• `/listowners` — List all extra owners.",
                    "• `/dmall` — Send an embed to every member via DM.",
                    "",
                    "**🔐 Bot Owner** (the person whose ID is in the `.env` file) can always use any command, even without a role.",
                ]
            },
            # ---------- NEW MODULES ----------
            "Staff Stats": {
                "description": "View ticket statistics and leave days for any staff member.",
                "commands": [
                    "`/staffstats @user` — Show tickets claimed, closed, total handled, leave days, and current leave status.",
                ]
            },
            "Leave System": {
                "description": "Request and manage staff leave directly through the bot.",
                "commands": [
                    "`/leavepanel` — Send the persistent leave panel (admin only).",
                    "`/leavesetup @role` — Set the 'On Leave' role (admin only).",
                    "`/leave` — Request leave or end leave early (TicketSupporter+).",
                    "Use the buttons on the leave panel for quick actions.",
                ]
            },
            "Owner Tools": {
                "description": "Commands for the server owner and extra owners.",
                "commands": [
                    "`/addowner @user` — Promote a user to extra owner.",
                    "`/removeowner @user` — Demote an extra owner.",
                    "`/listowners` — Show all extra owners.",
                    "`/dmall` — Send an embed to every server member.",
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
                    "Select a category from the dropdown below to browse available commands.\n"
                    "👉 Check the **Setup Guide** for role configuration and permissions."
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
        view = HelpView(self.bot)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(HelpCog(bot))