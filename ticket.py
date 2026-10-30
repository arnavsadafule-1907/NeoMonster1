import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import asyncio
import io
from datetime import datetime, timezone
from formatter import BotEmbed
from checks import admin_only, ticket_staff_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# ============================================================
#  PANEL EMOJIS
#  Animated: <a:name:id>    Static: <:name:id>    Unicode: 🎟️
# ============================================================
PANEL_EMOJIS = {
    "title":  "",
    "footer": "🛡️",
    "button": "",
}


# -------------------------------------------------------------------
#  Ticket View — buttons inside the ticket channel
# -------------------------------------------------------------------
class TicketView(discord.ui.View):
    def __init__(self, cog, ticket_type_name: str, claimed_by: int = None):
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_type_name = ticket_type_name
        self.claimed_by = claimed_by

        if claimed_by:
            self.claim_button.disabled = True
            self.claim_button.label = "Claimed"
            self.claim_button.style = discord.ButtonStyle.success

    async def _check_staff_permission(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.owner_ids:
            return True
        if interaction.user.id == interaction.guild.owner_id:
            return True
        allowed_roles = ["TicketSupporter", "Staff.exe", "admin.exe", "nuke.exe"]
        for role_name in allowed_roles:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in interaction.user.roles:
                return True
        await interaction.response.send_message(
            embed=BotEmbed.error("Permission Denied", "You need one of: TicketSupporter, Staff.exe, admin.exe, nuke.exe"),
            ephemeral=True
        )
        return False

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        if self.claimed_by is not None:
            await interaction.response.send_message(
                embed=BotEmbed.error("Already Claimed", f"This ticket is already claimed by <@{self.claimed_by}>."),
                ephemeral=True
            )
            return
        await self.cog.claim_ticket(interaction, self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await interaction.response.send_modal(CloseTicketModal(self.cog, interaction.channel))

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.success, custom_id="ticket_add_user")
    async def add_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await interaction.response.send_modal(AddUserModal(interaction.channel))

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, custom_id="ticket_remove_user")
    async def remove_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await interaction.response.send_modal(RemoveUserModal(interaction.channel))

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, custom_id="ticket_rename")
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await interaction.response.send_modal(RenameTicketModal(interaction.channel))


# -------------------------------------------------------------------
#  Ticket Type Picker — shown after clicking "Open Ticket"
# -------------------------------------------------------------------
class TicketTypePickerView(discord.ui.View):
    def __init__(self, cog, types):
        super().__init__(timeout=120)
        self.cog = cog

        for t in types[:20]:
            button = discord.ui.Button(
                label=t["name"][:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"ticket_pick_{t['name']}"
            )
            button.callback = self._make_callback(t["name"])
            self.add_item(button)

    def _make_callback(self, ticket_type_name: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.send_modal(TicketOpenModal(self.cog, ticket_type_name))
        return callback


# -------------------------------------------------------------------
#  Modals — ticket actions
# -------------------------------------------------------------------
class AddUserModal(discord.ui.Modal, title="Add User to Ticket"):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.user_id = discord.ui.TextInput(
            label="User ID",
            placeholder="Enter the user ID to add",
            required=True
        )
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.guild.fetch_member(int(self.user_id.value.strip()))
        except Exception:
            return await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        try:
            await self.channel.set_permissions(user, read_messages=True, send_messages=True)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ I lack permission to edit this channel.", ephemeral=True)
        await interaction.response.send_message(f"✅ Added {user.mention} to the ticket.", ephemeral=False)


class RemoveUserModal(discord.ui.Modal, title="Remove User from Ticket"):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.user_id = discord.ui.TextInput(
            label="User ID",
            placeholder="Enter the user ID to remove",
            required=True
        )
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.guild.fetch_member(int(self.user_id.value.strip()))
        except Exception:
            return await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        try:
            await self.channel.set_permissions(user, overwrite=None)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ I lack permission to edit this channel.", ephemeral=True)
        await interaction.response.send_message(f"✅ Removed {user.mention} from the ticket.", ephemeral=False)


class RenameTicketModal(discord.ui.Modal, title="Rename Ticket"):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.new_name = discord.ui.TextInput(
            label="New Name",
            placeholder="e.g., billing-issue",
            required=True,
            max_length=90
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.new_name.value.strip().replace(" ", "-").lower()
        try:
            await self.channel.edit(name=f"ticket-{new_name}")
        except discord.Forbidden:
            return await interaction.response.send_message("❌ I lack permission to rename this channel.", ephemeral=True)
        await interaction.response.send_message(f"✅ Ticket renamed to `{new_name}`", ephemeral=False)


class CloseTicketModal(discord.ui.Modal, title="Close Ticket"):
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Reason for closing (optional)",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
            default="No reason specified"
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.close_ticket_with_reason(interaction, self.reason.value.strip() or "No reason specified")


class TicketOpenModal(discord.ui.Modal, title="Open Ticket"):
    def __init__(self, cog, ticket_type_name: str):
        super().__init__()
        self.cog = cog
        self.ticket_type_name = ticket_type_name
        self.ign = discord.ui.TextInput(
            label="What's your IGN? (In-Game Name)",
            placeholder="e.g., NotPriyanshuFr",
            required=True,
            max_length=100
        )
        self.add_item(self.ign)
        self.reason = discord.ui.TextInput(
            label="Why are you opening the ticket?",
            placeholder="Explain your issue or request...",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.create_ticket(
            interaction,
            self.ticket_type_name,
            ign=self.ign.value.strip(),
            reason=self.reason.value.strip()
        )


# ============================================================
#  Panel Edit Modal — real text boxes, no \n needed
# ============================================================
class PanelEditModal(discord.ui.Modal, title="Edit Ticket Panel"):
    def __init__(self, cog, config):
        super().__init__()
        self.cog = cog

        existing_title = config["title"] if config and config["title"] else ""
        existing_desc = config["description"] if config and config["description"] else ""
        existing_img = config["image_url"] if config and config["image_url"] else ""
        existing_style = config["panel_style"] if config and config["panel_style"] else "dropdown"

        self.title_input = discord.ui.TextInput(
            label="Panel Title",
            placeholder="e.g., Create A Wish",
            default=existing_title,
            required=False,
            max_length=200
        )
        self.add_item(self.title_input)

        self.description_input = discord.ui.TextInput(
            label="Description / Guidelines",
            placeholder="Type normally. Press Enter for a new line.",
            default=existing_desc,
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )
        self.add_item(self.description_input)

        self.image_input = discord.ui.TextInput(
            label="Image URL (optional)",
            placeholder="https://example.com/banner.png",
            default=existing_img,
            required=False,
            max_length=500
        )
        self.add_item(self.image_input)

        self.style_input = discord.ui.TextInput(
            label="Style: dropdown or buttons",
            placeholder="dropdown",
            default=existing_style,
            required=False,
            max_length=10
        )
        self.add_item(self.style_input)

    async def on_submit(self, interaction: discord.Interaction):
        style = self.style_input.value.strip().lower()
        if style not in ("dropdown", "buttons"):
            style = "dropdown"

        await self.cog.set_panel_config(
            interaction.guild_id,
            title=self.title_input.value.strip() or None,
            description=self.description_input.value.strip() or None,
            image_url=self.image_input.value.strip() or None,
            panel_style=style
        )

        await interaction.response.send_message(
            embed=BotEmbed.success(
                "Panel Updated",
                f"Style: **{style}**\nUse `/ticketpanel send` to post the updated panel."
            ),
            ephemeral=True
        )


# ============================================================
#  Add Ticket Type Modal — fixed top-level class
# ============================================================
class AddTicketTypeModal(discord.ui.Modal, title="Add Ticket Type"):
    name = discord.ui.TextInput(
        label="Name",
        placeholder="e.g., Support, Report, Reward Claim",
        required=True,
        max_length=100
    )
    category_id = discord.ui.TextInput(
        label="Category ID",
        placeholder="Right-click a category → Copy ID",
        required=True,
        max_length=30
    )
    support_role_id = discord.ui.TextInput(
        label="Support Role ID (optional)",
        placeholder="Leave as 0 if no specific role",
        required=False,
        default="0",
        max_length=30
    )
    welcome_message = discord.ui.TextInput(
        label="Welcome Message",
        placeholder="{user} will be replaced with the member's mention.",
        required=False,
        style=discord.TextStyle.paragraph,
        default="Welcome {user}! Support staff will assist you shortly.",
        max_length=1000
    )

    def __init__(self, cog, guild, guild_id):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        # --- Parse category ID ---
        try:
            cat_id = int(self.category_id.value.strip())
        except ValueError:
            return await interaction.response.send_message(
                "❌ **Category ID** must be a number. Right-click a category → Copy ID.",
                ephemeral=True
            )

        # --- Parse support role ID ---
        role_id = 0
        raw_role = (self.support_role_id.value or "").strip()
        if raw_role and raw_role != "0":
            try:
                role_id = int(raw_role)
            except ValueError:
                return await interaction.response.send_message(
                    "❌ **Support Role ID** must be a number (or leave as 0).",
                    ephemeral=True
                )

        # --- Validate the category exists ---
        category = self.guild.get_channel(cat_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message(
                "❌ That ID does not point to a valid **category** in this server.",
                ephemeral=True
            )

        # --- Validate the role if provided ---
        if role_id:
            role = self.guild.get_role(role_id)
            if not role:
                return await interaction.response.send_message(
                    "❌ That ID does not point to a valid **role** in this server.",
                    ephemeral=True
                )

        name = self.name.value.strip()
        welcome = self.welcome_message.value.strip() if self.welcome_message.value else None

        await self.cog.add_ticket_type(
            self.guild_id,
            name,
            cat_id,
            role_id,
            welcome
        )

        await interaction.response.send_message(
            embed=BotEmbed.success(
                "Ticket Type Added",
                f"**{name}** tickets are now available.\nUse `/ticketpanel send` to refresh the panel."
            ),
            ephemeral=True
        )


# -------------------------------------------------------------------
#  Ticket Cog
# -------------------------------------------------------------------
class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._claim_locks = {}

    async def _ensure_tables(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS ticket_types (
                guild_id INTEGER, name TEXT, category_id INTEGER,
                support_role_id INTEGER DEFAULT 0, welcome_message TEXT,
                PRIMARY KEY (guild_id, name))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS ticket_counter (
                guild_id INTEGER PRIMARY KEY, counter INTEGER DEFAULT 0)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS ticket_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER,
                ticket_number INTEGER, channel_id INTEGER UNIQUE,
                user_id INTEGER, open_time TEXT, claimed_by INTEGER, ticket_type TEXT)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS ticket_panel_config (
                guild_id INTEGER PRIMARY KEY, title TEXT, description TEXT,
                image_url TEXT, panel_style TEXT DEFAULT 'dropdown')""")
            try:
                await db.execute("ALTER TABLE ticket_panel_config ADD COLUMN panel_style TEXT DEFAULT 'dropdown'")
            except Exception:
                pass
            await db.commit()

    async def get_ticket_types(self, guild_id: int):
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_types WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchall()

    async def add_ticket_type(self, guild_id, name, category_id, support_role_id, welcome_message):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ticket_types (guild_id, name, category_id, support_role_id, welcome_message) VALUES (?, ?, ?, ?, ?)",
                (guild_id, name, category_id, support_role_id, welcome_message)
            )
            await db.commit()

    async def remove_ticket_type(self, guild_id, name):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM ticket_types WHERE guild_id = ? AND name = ?", (guild_id, name))
            await db.commit()

    async def get_ticket_type(self, guild_id, name):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_types WHERE guild_id = ? AND name = ?", (guild_id, name))
            return await cursor.fetchone()

    async def _next_ticket_number(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT counter FROM ticket_counter WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            if row:
                num = row[0] + 1
                await db.execute("UPDATE ticket_counter SET counter = ? WHERE guild_id = ?", (num, guild_id))
            else:
                num = 1
                await db.execute("INSERT INTO ticket_counter (guild_id, counter) VALUES (?, ?)", (guild_id, num))
            await db.commit()
            return num

    async def save_ticket_metadata(self, guild_id, ticket_number, channel_id, user_id, ticket_type):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO ticket_metadata (guild_id, ticket_number, channel_id, user_id, open_time, ticket_type) VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, ticket_number, channel_id, user_id, datetime.now(timezone.utc).isoformat(), ticket_type)
            )
            await db.commit()

    async def update_ticket_claim(self, channel_id, claimed_by):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE ticket_metadata SET claimed_by = ? WHERE channel_id = ?", (claimed_by, channel_id))
            await db.commit()

    async def get_ticket_metadata(self, channel_id):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_metadata WHERE channel_id = ?", (channel_id,))
            return await cursor.fetchone()

    async def delete_ticket_metadata(self, channel_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM ticket_metadata WHERE channel_id = ?", (channel_id,))
            await db.commit()

    async def _log(self, guild, user, action, ticket_channel=None, extra_info="", file=None, ticket_name=None, channel_name=None):
        logger_cog = self.bot.get_cog("ServerLogger")
        if logger_cog:
            await logger_cog.log_ticket_action(
                guild, user, action, ticket_channel=ticket_channel,
                extra_info=extra_info, file=file, ticket_name=ticket_name, channel_name=channel_name
            )

    @staticmethod
    async def increment_staff_stat(guild_id, user_id, column):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                f"INSERT INTO staff_stats (guild_id, user_id, {column}) VALUES (?, ?, 1) "
                f"ON CONFLICT(guild_id, user_id) DO UPDATE SET {column} = {column} + 1",
                (guild_id, user_id)
            )
            await db.commit()

    async def get_panel_config(self, guild_id):
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_panel_config WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchone()

    async def set_panel_config(self, guild_id, title=None, description=None,
                               image_url=None, panel_style=None):
        await self._ensure_tables()

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_panel_config WHERE guild_id = ?", (guild_id,))
            existing = await cursor.fetchone()

            if existing:
                new_title = title if title is not None else existing["title"]
                new_desc = description if description is not None else existing["description"]
                new_img = image_url if image_url is not None else existing["image_url"]
                new_style = panel_style if panel_style is not None else (existing["panel_style"] or "dropdown")

                await db.execute(
                    "UPDATE ticket_panel_config SET title=?, description=?, image_url=?, panel_style=? WHERE guild_id=?",
                    (new_title, new_desc, new_img, new_style, guild_id)
                )
            else:
                await db.execute(
                    "INSERT INTO ticket_panel_config (guild_id, title, description, image_url, panel_style) VALUES (?, ?, ?, ?, ?)",
                    (guild_id, title, description, image_url, panel_style or "dropdown")
                )
            await db.commit()

    # ============================================================
    #  PANEL COMMANDS
    # ============================================================
    panel_group = app_commands.Group(name="ticketpanel", description="Manage the ticket panel")

    @panel_group.command(name="send", description="Send the ticket panel in this channel")
    @admin_only()
    async def panel_send(self, interaction: discord.Interaction):
        await self._ensure_tables()
        types = await self.get_ticket_types(interaction.guild_id)
        if not types:
            return await interaction.response.send_message(
                embed=BotEmbed.error("No Ticket Types", "Use `/tickettype add` to create at least one ticket type first."),
                ephemeral=True
            )

        config = await self.get_panel_config(interaction.guild_id)
        title = (config["title"] if config and config["title"] else "Create A Wish")
        description = (config["description"] if config and config["description"]
                       else "Select the type of ticket you'd like to open below.")
        image_url = config["image_url"] if config and config["image_url"] else None
        style = (config["panel_style"] if config and config["panel_style"] else "dropdown")

        embed = discord.Embed(
            title=f"{PANEL_EMOJIS['title']} {title}",
            description=description,
            color=0x2B2D31
        )

        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"{PANEL_EMOJIS['footer']} Powered by NeoMonster")

        view = discord.ui.View(timeout=None)

        if style == "buttons":
            open_button = discord.ui.Button(
                label="Open Ticket",
                style=discord.ButtonStyle.blurple,
                emoji=PANEL_EMOJIS["button"],
                custom_id="ticket_open_main"
            )
            open_button.callback = self._make_open_ticket_callback(types)
            view.add_item(open_button)
        else:
            options = [
                discord.SelectOption(
                    label=t["name"][:100],
                    description=f"Open a {t['name'].lower()} ticket"[:100],
                    value=t["name"]
                )
                for t in types[:25]
            ]
            select_menu = discord.ui.Select(
                placeholder="Select a ticket type...",
                options=options,
                custom_id="ticket_panel_select",
                min_values=1, max_values=1
            )
            select_menu.callback = self._make_select_callback(select_menu)
            view.add_item(select_menu)

        await interaction.response.send_message(embed=embed, view=view)

    def _make_open_ticket_callback(self, types):
        async def callback(interaction: discord.Interaction):
            if len(types) == 1:
                await interaction.response.send_modal(TicketOpenModal(self, types[0]["name"]))
            else:
                picker = TicketTypePickerView(self, types)
                await interaction.response.send_message(
                    "**Select a ticket type:**",
                    view=picker,
                    ephemeral=True
                )
        return callback

    def _make_select_callback(self, select_menu):
        async def callback(interaction: discord.Interaction):
            selected = select_menu.values[0]
            await interaction.response.send_modal(TicketOpenModal(self, selected))
        return callback

    @panel_group.command(name="edit", description="Open a form to customise the panel")
    @admin_only()
    async def panel_edit(self, interaction: discord.Interaction):
        config = await self.get_panel_config(interaction.guild_id)
        await interaction.response.send_modal(PanelEditModal(self, config))

    @panel_group.command(name="reset", description="Reset the ticket panel to defaults")
    @admin_only()
    async def panel_reset(self, interaction: discord.Interaction):
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM ticket_panel_config WHERE guild_id = ?", (interaction.guild_id,))
            await db.commit()
        await interaction.response.send_message(
            embed=BotEmbed.success("Panel Reset", "Panel has been restored to defaults."),
            ephemeral=True
        )

    # ============================================================
    #  CREATE TICKET
    # ============================================================
    async def create_ticket(self, interaction, ticket_type_name, ign=None, reason=None):
        ticket_type = await self.get_ticket_type(interaction.guild_id, ticket_type_name)
        if not ticket_type:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Invalid Ticket Type", "That ticket type no longer exists."),
                ephemeral=True
            )

        category = interaction.guild.get_channel(ticket_type["category_id"])
        if not category:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Missing Category", "The category for this ticket type has been deleted."),
                ephemeral=True
            )

        ticket_num = await self._next_ticket_number(interaction.guild_id)
        channel_name = f"ticket-{ticket_num:04d}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        if ticket_type["support_role_id"]:
            role = interaction.guild.get_role(ticket_type["support_role_id"])
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_supporter_role = discord.utils.get(interaction.guild.roles, name="TicketSupporter")
        if ticket_supporter_role and ticket_supporter_role not in overwrites:
            overwrites[ticket_supporter_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ticket_channel = await category.create_text_channel(
                name=channel_name, overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user}"
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Permission Denied", "I need `Manage Channels` in the ticket category."),
                ephemeral=True
            )

        await self.save_ticket_metadata(interaction.guild_id, ticket_num, ticket_channel.id, interaction.user.id, ticket_type_name)

        support_role = None
        if ticket_type["support_role_id"]:
            support_role = interaction.guild.get_role(ticket_type["support_role_id"])
        if not support_role:
            support_role = ticket_supporter_role

        if support_role:
            await ticket_channel.send(
                f"{support_role.mention} A new ticket has been opened!",
                allowed_mentions=discord.AllowedMentions(roles=True)
            )

        welcome_text = ticket_type["welcome_message"] or f"Welcome {interaction.user.mention}! Support staff will assist you shortly."
        welcome_text = welcome_text.replace("{user}", interaction.user.mention)

        extra_info = ""
        if ign:
            extra_info += f"\n**IGN:** {ign}"
        if reason:
            extra_info += f"\n**Reason:** {reason}"

        send_ping = False
        if "@here" in welcome_text:
            send_ping = True
            welcome_text = welcome_text.replace("@here", "").strip()

        welcome_embed = discord.Embed(
            title=f"🎫 {ticket_type_name} Ticket",
            description=welcome_text + extra_info,
            color=0x3B82F6
        )
        welcome_embed.set_footer(text=f"Ticket #{ticket_num:04d}")

        if send_ping:
            await ticket_channel.send(content="@here", allowed_mentions=discord.AllowedMentions(everyone=False, here=True))

        view = TicketView(self, ticket_type_name, claimed_by=None)
        await ticket_channel.send(embed=welcome_embed, view=view)

        await interaction.response.send_message(
            embed=BotEmbed.info("Ticket Created", f"Your ticket channel: {ticket_channel.mention}"),
            ephemeral=True
        )
        await self._log(interaction.guild, interaction.user, "open", ticket_channel, channel_name=channel_name)

    async def claim_ticket(self, interaction, view: TicketView = None):
        lock = self._claim_locks.get(interaction.channel.id)
        if lock is None:
            lock = asyncio.Lock()
            self._claim_locks[interaction.channel.id] = lock

        async with lock:
            if not interaction.channel.name.startswith("ticket-"):
                return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)

            metadata = await self.get_ticket_metadata(interaction.channel.id)
            if not metadata:
                return await interaction.response.send_message(
                    embed=BotEmbed.error("Not a Ticket", "This channel is no longer a valid ticket."),
                    ephemeral=True
                )

            if metadata["claimed_by"]:
                return await interaction.response.send_message(
                    embed=BotEmbed.error("Already Claimed", f"Already claimed by <@{metadata['claimed_by']}>."),
                    ephemeral=True
                )

            new_name = f"claimed-{interaction.user.name}"
            try:
                await interaction.channel.edit(name=new_name)
            except discord.Forbidden:
                pass

            await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
            await self.update_ticket_claim(interaction.channel.id, interaction.user.id)

            claimed_view = TicketView(self, metadata["ticket_type"], claimed_by=interaction.user.id)
            try:
                await interaction.message.edit(view=claimed_view)
            except Exception:
                pass

            await interaction.response.send_message(
                embed=BotEmbed.success("Claimed", f"Ticket claimed by {interaction.user.mention}."),
                ephemeral=False
            )
            await self._log(interaction.guild, interaction.user, "claim", interaction.channel, channel_name=interaction.channel.name)
            await self.increment_staff_stat(interaction.guild.id, interaction.user.id, "tickets_claimed")

        self._claim_locks.pop(interaction.channel.id, None)

    async def close_ticket_with_reason(self, interaction, reason):
        if not (interaction.channel.name.startswith("ticket-") or interaction.channel.name.startswith("claimed-")):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)

        channel_name = interaction.channel.name
        await interaction.response.send_message("🔒 Closing ticket and generating transcript...", ephemeral=True)

        metadata = await self.get_ticket_metadata(interaction.channel.id)
        if not metadata:
            return await interaction.followup.send("No metadata found for this ticket.", ephemeral=True)

        messages = []
        try:
            async for msg in interaction.channel.history(limit=500, oldest_first=True):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = msg.content or "(no text)"
                if msg.attachments:
                    content += "\n[Attachments: " + ", ".join([a.url for a in msg.attachments]) + "]"
                messages.append(f"[{ts}] {msg.author.name}: {content}")
        except discord.Forbidden:
            pass

        transcript = f"Transcript for ticket #{metadata['ticket_number']} ({metadata['ticket_type']})\n"
        transcript += f"Opened by: <@{metadata['user_id']}>\n"
        transcript += f"Opened at: {metadata['open_time']}\n"
        transcript += f"Claimed by: <@{metadata['claimed_by']}>" if metadata['claimed_by'] else "Not claimed"
        transcript += f"\nClosed by: {interaction.user.mention}\n"
        transcript += f"Close Reason: {reason}\n"
        transcript += f"Closed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        transcript += "\n".join(messages)

        file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"ticket-{metadata['ticket_number']}.txt")

        await self._log(
            interaction.guild, interaction.user, "close", None,
            extra_info=f"Reason: {reason}", file=file,
            ticket_name=metadata["ticket_type"], channel_name=channel_name
        )

        await self.increment_staff_stat(interaction.guild.id, interaction.user.id, "tickets_closed")
        await self.delete_ticket_metadata(interaction.channel.id)
        await asyncio.sleep(2)
        await interaction.channel.delete(reason="Ticket closed")

    # ============================================================
    #  STAFF SLASH COMMANDS
    # ============================================================
    @app_commands.command(name="ticket_add", description="Add a user to the current ticket")
    @app_commands.describe(user="User to add")
    @ticket_staff_only()
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
        await interaction.response.send_message(embed=BotEmbed.success("User Added", f"{user.mention} can now see this ticket."))

    @app_commands.command(name="ticket_remove", description="Remove a user from the current ticket")
    @app_commands.describe(user="User to remove")
    @ticket_staff_only()
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=BotEmbed.success("User Removed", f"{user.mention} has been removed."))

    @app_commands.command(name="ticket_rename", description="Rename the current ticket")
    @app_commands.describe(name="New name (e.g., billing-issue)")
    @ticket_staff_only()
    async def ticket_rename(self, interaction: discord.Interaction, name: str):
        new_name = name.replace(" ", "-").lower()
        await interaction.channel.edit(name=f"ticket-{new_name}")
        await interaction.response.send_message(embed=BotEmbed.success("Renamed", f"Ticket renamed to `{new_name}`."))

    @app_commands.command(name="ticket_close", description="Close the current ticket")
    @ticket_staff_only()
    async def ticket_close_slash(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CloseTicketModal(self, interaction.channel))

    @app_commands.command(name="ticket_claim", description="Claim the current ticket")
    @ticket_staff_only()
    async def ticket_claim_slash(self, interaction: discord.Interaction):
        metadata = await self.get_ticket_metadata(interaction.channel.id)
        if metadata and metadata["claimed_by"]:
            return await interaction.response.send_message(
                embed=BotEmbed.error("Already Claimed", f"Already claimed by <@{metadata['claimed_by']}>."),
                ephemeral=True
            )

        new_name = f"claimed-{interaction.user.name}"
        try:
            await interaction.channel.edit(name=new_name)
        except discord.Forbidden:
            pass

        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await self.update_ticket_claim(interaction.channel.id, interaction.user.id)

        claimed_view = TicketView(self, metadata["ticket_type"], claimed_by=interaction.user.id)
        try:
            async for msg in interaction.channel.history(limit=10):
                if msg.author == self.bot.user and msg.components:
                    await msg.edit(view=claimed_view)
                    break
        except Exception:
            pass

        await interaction.response.send_message(embed=BotEmbed.success("Claimed", f"Ticket claimed by {interaction.user.mention}."))
        await self._log(interaction.guild, interaction.user, "claim", interaction.channel, channel_name=interaction.channel.name)
        await self.increment_staff_stat(interaction.guild.id, interaction.user.id, "tickets_claimed")

    # ============================================================
    #  TICKET TYPE MANAGEMENT
    # ============================================================
    @app_commands.command(name="tickettype", description="Manage ticket types (add / remove)")
    @app_commands.describe(action="Add or remove a ticket type")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
    ])
    @admin_only()
    async def ticket_type_manage(self, interaction: discord.Interaction, action: str):
        if action == "add":
            modal = AddTicketTypeModal(self, interaction.guild, interaction.guild_id)
            await interaction.response.send_modal(modal)
        elif action == "remove":
            await self._remove_ticket_type_menu(interaction)

    async def _remove_ticket_type_menu(self, interaction):
        types = await self.get_ticket_types(interaction.guild_id)
        if not types:
            return await interaction.response.send_message(
                embed=BotEmbed.error("No Ticket Types", "There are no ticket types to remove."),
                ephemeral=True
            )

        options = [
            discord.SelectOption(label=t["name"], description=f"Remove {t['name']} tickets", emoji="🗑️")
            for t in types
        ]
        select_menu = discord.ui.Select(
            placeholder="Select a ticket type to remove...",
            options=options, custom_id="ticket_remove_select",
            min_values=1, max_values=1
        )
        view = discord.ui.View(timeout=60)
        view.add_item(select_menu)

        async def select_callback(inter: discord.Interaction):
            selected = select_menu.values[0]
            await self.remove_ticket_type(inter.guild_id, selected)
            await inter.response.send_message(
                embed=BotEmbed.success("Ticket Type Removed", f"**{selected}** tickets have been disabled."),
                ephemeral=True
            )
            view.stop()

        select_menu.callback = select_callback
        await interaction.response.send_message("Choose a ticket type to remove:", view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Ticket(bot))