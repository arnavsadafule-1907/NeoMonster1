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

# -------------------------------------------------------------------
# Ticket View (buttons for the ticket channel)
# -------------------------------------------------------------------
class TicketView(discord.ui.View):
    def __init__(self, cog, ticket_type_name: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_type_name = ticket_type_name

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
            embed=BotEmbed.error("Permission Denied", "You need one of these roles: TicketSupporter, Staff.exe, admin.exe, nuke.exe"),
            ephemeral=True
        )
        return False

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await self.cog.claim_ticket(interaction)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await interaction.response.send_modal(CloseTicketModal(self.cog, interaction.channel))

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.success, custom_id="ticket_add_user")
    async def add_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await self.cog.add_user_modal(interaction)

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, custom_id="ticket_remove_user")
    async def remove_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await self.cog.remove_user_modal(interaction)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, custom_id="ticket_rename")
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff_permission(interaction):
            return
        await self.cog.rename_ticket_modal(interaction)


# -------------------------------------------------------------------
# Modals
# -------------------------------------------------------------------
class AddUserModal(discord.ui.Modal, title="Add User to Ticket"):
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.user_id = discord.ui.TextInput(label="User ID", placeholder="Enter the user ID to add", required=True)
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.guild.fetch_member(int(self.user_id.value))
        except:
            return await interaction.response.send_message("Invalid user ID.", ephemeral=True)
        await self.channel.set_permissions(user, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"Added {user.mention} to the ticket.", ephemeral=False)

class RemoveUserModal(discord.ui.Modal, title="Remove User from Ticket"):
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.user_id = discord.ui.TextInput(label="User ID", placeholder="Enter the user ID to remove", required=True)
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.guild.fetch_member(int(self.user_id.value))
        except:
            return await interaction.response.send_message("Invalid user ID.", ephemeral=True)
        await self.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(f"Removed {user.mention} from the ticket.", ephemeral=False)

class RenameTicketModal(discord.ui.Modal, title="Rename Ticket"):
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.new_name = discord.ui.TextInput(label="New Name", placeholder="e.g., billing-issue", required=True)
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.new_name.value.replace(" ", "-").lower()
        await self.channel.edit(name=f"ticket-{new_name}")
        await interaction.response.send_message(f"Ticket renamed to `{new_name}`", ephemeral=False)

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

# --- NEW MODAL FOR OPENING A TICKET ---
class TicketOpenModal(discord.ui.Modal, title="Open Ticket"):
    def __init__(self, cog, ticket_type_name: str):
        super().__init__()
        self.cog = cog
        self.ticket_type_name = ticket_type_name
        self.ign = discord.ui.TextInput(
            label="What's your IGN? (In‑Game Name)",
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


# -------------------------------------------------------------------
# Ticket Cog
# -------------------------------------------------------------------
class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================================================================
    #  DATABASE HELPERS
    # ================================================================
    async def get_ticket_types(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_types WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchall()

    async def add_ticket_type(self, guild_id: int, name: str, category_id: int, support_role_id: int, welcome_message: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ticket_types (guild_id, name, category_id, support_role_id, welcome_message) VALUES (?, ?, ?, ?, ?)",
                (guild_id, name, category_id, support_role_id, welcome_message)
            )
            await db.commit()

    async def remove_ticket_type(self, guild_id: int, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM ticket_types WHERE guild_id = ? AND name = ?", (guild_id, name))
            await db.commit()

    async def get_ticket_type(self, guild_id: int, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_types WHERE guild_id = ? AND name = ?", (guild_id, name))
            return await cursor.fetchone()

    async def _next_ticket_number(self, guild_id: int) -> int:
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

    async def _log(self, guild, user, action, ticket_channel=None, extra_info="", file=None):
        logger_cog = self.bot.get_cog("ServerLogger")
        if logger_cog:
            await logger_cog.log_ticket_action(guild, user, action, ticket_channel, extra_info, file=file)

    # ================================================================
    #  TICKET PANEL
    # ================================================================
    @app_commands.command(name="ticketpanel", description="Send the ticket creation panel in the current channel")
    @admin_only()
    async def ticket_panel(self, interaction: discord.Interaction):
        types = await self.get_ticket_types(interaction.guild_id)
        if not types:
            embed = BotEmbed.error("No Ticket Types", "Use `/tickettype add` to create at least one ticket type first.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        options = [discord.SelectOption(label=t["name"], description=f"Open a {t['name'].lower()} ticket", emoji="🎟️") for t in types]
        select_menu = discord.ui.Select(
            placeholder="Select a ticket type...",
            options=options,
            custom_id="ticket_panel_select",
            min_values=1, max_values=1
        )

        async def select_callback(interaction: discord.Interaction):
            selected_type = select_menu.values[0]
            await interaction.response.send_modal(TicketOpenModal(self, selected_type))

        select_menu.callback = select_callback
        view = discord.ui.View(timeout=None)
        view.add_item(select_menu)

        embed = discord.Embed(title="🎫 Support Tickets", description="Select the type of ticket you'd like to open from the dropdown below.", color=0x3B82F6)
        embed.set_footer(text="NeoMonster • Ticket System")
        await interaction.response.send_message(embed=embed, view=view)

    # --- MODIFIED create_ticket: always pings TicketSupporter role ---
    async def create_ticket(self, interaction: discord.Interaction, ticket_type_name: str, ign: str = None, reason: str = None):
        ticket_type = await self.get_ticket_type(interaction.guild_id, ticket_type_name)
        if not ticket_type:
            embed = BotEmbed.error("Invalid Ticket Type", "That ticket type no longer exists.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        category = interaction.guild.get_channel(ticket_type["category_id"])
        if not category:
            embed = BotEmbed.error("Missing Category", "The category for this ticket type has been deleted.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

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

        try:
            ticket_channel = await category.create_text_channel(
                name=channel_name, overwrites=overwrites, reason=f"Ticket opened by {interaction.user}"
            )
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I need `Manage Channels` in the ticket category.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await self.save_ticket_metadata(interaction.guild_id, ticket_num, ticket_channel.id, interaction.user.id, ticket_type_name)

        # --- STAFF PING: always try to ping the TicketSupporter role ---
        ticket_supporter = discord.utils.get(interaction.guild.roles, name="TicketSupporter")
        if ticket_supporter:
            await ticket_channel.send(
                f"{ticket_supporter.mention} A new ticket has been opened!",
                allowed_mentions=discord.AllowedMentions(roles=True)
            )

        # --- Welcome message (with @here or custom text) ---
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

        full_description = welcome_text + extra_info

        welcome_embed = discord.Embed(
            title=f"🎫 {ticket_type_name} Ticket",
            description=full_description,
            color=0x3B82F6
        )

        if send_ping:
            await ticket_channel.send(content="@here", allowed_mentions=discord.AllowedMentions(everyone=False, here=True))

        await ticket_channel.send(embed=welcome_embed, view=TicketView(self, ticket_type_name))

        embed = BotEmbed.info("Ticket Created", f"Your ticket channel: {ticket_channel.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._log(interaction.guild, interaction.user, "open", ticket_channel)

    # ================================================================
    #  BUTTON HANDLERS (unchanged)
    # ================================================================
    async def claim_ticket(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await self.update_ticket_claim(interaction.channel.id, interaction.user.id)
        await interaction.response.send_message(f"✅ Ticket claimed by {interaction.user.mention}", ephemeral=False)
        await self._log(interaction.guild, interaction.user, "claim", interaction.channel)

    async def close_ticket_with_reason(self, interaction: discord.Interaction, reason: str):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)

        await interaction.response.send_message("🔒 Closing ticket and generating transcript...", ephemeral=True)

        metadata = await self.get_ticket_metadata(interaction.channel.id)
        if not metadata:
            await interaction.followup.send("No metadata found for this ticket.", ephemeral=True)
            return

        messages = []
        try:
            async for msg in interaction.channel.history(limit=500, oldest_first=True):
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = msg.content or "(no text)"
                if msg.attachments:
                    content += "\n[Attachments: " + ", ".join([a.url for a in msg.attachments]) + "]"
                messages.append(f"[{timestamp}] {msg.author.name}#{msg.author.discriminator}: {content}")
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

        file = discord.File(
            io.BytesIO(transcript.encode('utf-8')),
            filename=f"ticket-{metadata['ticket_number']}.txt",
            description="Ticket transcript"
        )

        log_embed = discord.Embed(title="🎫 Ticket Closed", color=0x3B82F6, timestamp=datetime.now(timezone.utc))
        log_embed.add_field(name="Ticket ID", value=f"#{metadata['ticket_number']}", inline=True)
        log_embed.add_field(name="Opened By", value=f"<@{metadata['user_id']}>", inline=True)
        log_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Open Time", value=metadata['open_time'][:19].replace('T', ' '), inline=True)
        log_embed.add_field(name="Claimed By", value=f"<@{metadata['claimed_by']}>" if metadata['claimed_by'] else "Not claimed", inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)

        await self._log(interaction.guild, interaction.user, "close", interaction.channel, extra_info=f"Reason: {reason}", file=file)
        await self.delete_ticket_metadata(interaction.channel.id)
        await asyncio.sleep(2)
        await interaction.channel.delete(reason="Ticket closed")

    async def add_user_modal(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.response.send_modal(AddUserModal(self, interaction.channel))

    async def remove_user_modal(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.response.send_modal(RemoveUserModal(self, interaction.channel))

    async def rename_ticket_modal(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.response.send_modal(RenameTicketModal(self, interaction.channel))

    # ================================================================
    #  STAFF SLASH COMMANDS (unchanged)
    # ================================================================
    @app_commands.command(name="ticket_add", description="Add a user to the current ticket")
    @app_commands.describe(user="User to add")
    @ticket_staff_only()
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
        await interaction.response.send_message(embed=BotEmbed.success("User Added", f"{user.mention} can now see this ticket."))

    @app_commands.command(name="ticket_remove", description="Remove a user from the current ticket")
    @app_commands.describe(user="User to remove")
    @ticket_staff_only()
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=BotEmbed.success("User Removed", f"{user.mention} has been removed."))

    @app_commands.command(name="ticket_rename", description="Rename the current ticket")
    @app_commands.describe(name="New name (e.g., billing-issue)")
    @ticket_staff_only()
    async def ticket_rename(self, interaction: discord.Interaction, name: str):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        new_name = name.replace(" ", "-").lower()
        await interaction.channel.edit(name=f"ticket-{new_name}")
        await interaction.response.send_message(embed=BotEmbed.success("Renamed", f"Ticket renamed to `{new_name}`."))

    @app_commands.command(name="ticket_close", description="Close the current ticket (prompts for reason)")
    @ticket_staff_only()
    async def ticket_close_slash(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.response.send_modal(CloseTicketModal(self, interaction.channel))

    @app_commands.command(name="ticket_claim", description="Claim the current ticket")
    @ticket_staff_only()
    async def ticket_claim_slash(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await self.update_ticket_claim(interaction.channel.id, interaction.user.id)
        await interaction.response.send_message(embed=BotEmbed.success("Claimed", f"Ticket claimed by {interaction.user.mention}."))
        await self._log(interaction.guild, interaction.user, "claim", interaction.channel)

    # ================================================================
    #  TICKET TYPE MANAGEMENT (unchanged)
    # ================================================================
    @app_commands.command(name="tickettype", description="Manage ticket types (add / remove)")
    @app_commands.describe(action="Add or remove a ticket type")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
    ])
    @admin_only()
    async def ticket_type_manage(self, interaction: discord.Interaction, action: str):
        if action == "add":
            await self._add_ticket_type_modal(interaction)
        elif action == "remove":
            await self._remove_ticket_type_menu(interaction)

    async def _add_ticket_type_modal(self, interaction: discord.Interaction):
        class AddTypeModal(discord.ui.Modal, title="Add Ticket Type"):
            name = discord.ui.TextInput(label="Name", placeholder="e.g., Support, Report, Reward Claim", required=True)
            category_id = discord.ui.TextInput(label="Category ID", placeholder="Right-click a category and copy ID", required=True)
            support_role_id = discord.ui.TextInput(label="Support Role ID", placeholder="Role ID that can manage tickets (optional)", required=False, default="0")
            welcome_message = discord.ui.TextInput(
                label="Welcome Message",
                placeholder="{user} will be replaced. Include @here to ping staff.",
                required=False,
                style=discord.TextStyle.paragraph,
                default="Welcome {user}! Support staff will assist you shortly."
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    cat_id = int(self.category_id.value)
                    role_id = int(self.support_role_id.value) if self.support_role_id.value else 0
                except ValueError:
                    return await modal_interaction.response.send_message("Invalid category or role ID.", ephemeral=True)
                category = interaction.guild.get_channel(cat_id)
                if not category or not isinstance(category, discord.CategoryChannel):
                    return await modal_interaction.response.send_message("That category ID does not point to a valid category.", ephemeral=True)
                await self.cog.add_ticket_type(interaction.guild_id, self.name.value, cat_id, role_id, self.welcome_message.value or None)
                embed = BotEmbed.success("Ticket Type Added", f"**{self.name.value}** tickets are now available.")
                await modal_interaction.response.send_message(embed=embed, ephemeral=True)

        modal = AddTypeModal()
        modal.cog = self
        await interaction.response.send_modal(modal)

    async def _remove_ticket_type_menu(self, interaction: discord.Interaction):
        types = await self.get_ticket_types(interaction.guild_id)
        if not types:
            embed = BotEmbed.error("No Ticket Types", "There are no ticket types to remove.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        options = [discord.SelectOption(label=t["name"], description=f"Remove {t['name']} tickets", emoji="🗑️") for t in types]
        select_menu = discord.ui.Select(
            placeholder="Select a ticket type to remove...",
            options=options,
            custom_id="ticket_remove_select",
            min_values=1, max_values=1
        )
        async def select_callback(interaction: discord.Interaction):
            selected = select_menu.values[0]
            await self.remove_ticket_type(interaction.guild_id, selected)
            embed = BotEmbed.success("Ticket Type Removed", f"**{selected}** tickets have been disabled.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            view.stop()

        select_menu.callback = select_callback
        view = discord.ui.View(timeout=60)
        view.add_item(select_menu)
        await interaction.response.send_message("Choose a ticket type to remove:", view=view, ephemeral=True)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS ticket_types (
            guild_id INTEGER, name TEXT, category_id INTEGER, support_role_id INTEGER DEFAULT 0, welcome_message TEXT,
            PRIMARY KEY (guild_id, name))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS ticket_channels (
            channel_id INTEGER PRIMARY KEY, guild_id INTEGER, ticket_type TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS ticket_counter (
            guild_id INTEGER PRIMARY KEY, counter INTEGER DEFAULT 0)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS ticket_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, ticket_number INTEGER, channel_id INTEGER UNIQUE,
            user_id INTEGER, open_time TEXT, claimed_by INTEGER, ticket_type TEXT)""")
        await db.commit()
    await bot.add_cog(Ticket(bot))