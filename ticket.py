import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import asyncio
from formatter import BotEmbed
from checks import admin_only

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# -------------------------------------------------------------------
# Ticket View (buttons for the ticket channel)
# -------------------------------------------------------------------
class TicketView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.claim_ticket(interaction)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.close_ticket(interaction)

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.success, custom_id="ticket_add_user")
    async def add_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.add_user_modal(interaction)

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, custom_id="ticket_remove_user")
    async def remove_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.remove_user_modal(interaction)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, custom_id="ticket_rename")
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.rename_ticket_modal(interaction)

# -------------------------------------------------------------------
# Modals for user input
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
        """Return a list of all configured ticket types for a guild."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_types WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchall()

    async def add_ticket_type(self, guild_id: int, name: str, category_id: int, support_role_id: int, welcome_message: str):
        """Add a new ticket type."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ticket_types (guild_id, name, category_id, support_role_id, welcome_message) VALUES (?, ?, ?, ?, ?)",
                (guild_id, name, category_id, support_role_id, welcome_message)
            )
            await db.commit()

    async def remove_ticket_type(self, guild_id: int, name: str):
        """Remove a ticket type."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM ticket_types WHERE guild_id = ? AND name = ?", (guild_id, name))
            await db.commit()

    async def get_ticket_type(self, guild_id: int, name: str):
        """Get settings for a specific ticket type."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ticket_types WHERE guild_id = ? AND name = ?", (guild_id, name))
            return await cursor.fetchone()

    # ================================================================
    #  TICKET PANEL (persistent dropdown)
    # ================================================================
    @app_commands.command(name="ticketpanel", description="Send the ticket creation panel in the current channel")
    @admin_only()
    async def ticket_panel(self, interaction: discord.Interaction):
        types = await self.get_ticket_types(interaction.guild_id)
        if not types:
            embed = BotEmbed.error("No Ticket Types", "Use `/tickettype add` to create at least one ticket type first.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Build a select menu with all ticket types
        options = []
        for t in types:
            options.append(
                discord.SelectOption(
                    label=t["name"],
                    description=f"Open a {t['name'].lower()} ticket",
                    emoji="🎟️"
                )
            )

        select_menu = discord.ui.Select(
            placeholder="Select a ticket type...",
            options=options,
            custom_id="ticket_panel_select",
            min_values=1,
            max_values=1,
        )

        async def select_callback(interaction: discord.Interaction):
            selected_type = select_menu.values[0]
            await self.create_ticket(interaction, selected_type)

        select_menu.callback = select_callback

        view = discord.ui.View(timeout=None)
        view.add_item(select_menu)

        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Select the type of ticket you'd like to open from the dropdown below.",
            color=0x3B82F6
        )
        embed.set_footer(text="NeoMonster • Ticket System")

        await interaction.response.send_message(embed=embed, view=view)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type_name: str):
        """Internal method to create a ticket channel when a user selects an option."""
        ticket_type = await self.get_ticket_type(interaction.guild_id, ticket_type_name)
        if not ticket_type:
            embed = BotEmbed.error("Invalid Ticket Type", "That ticket type no longer exists.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        category = interaction.guild.get_channel(ticket_type["category_id"])
        if not category:
            embed = BotEmbed.error("Missing Category", "The category for this ticket type has been deleted.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Build channel name
        channel_name = f"ticket-{interaction.user.name}-{ticket_type_name.lower().replace(' ', '-')}"
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
                name=channel_name,
                overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user}"
            )
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I need `Manage Channels` in the ticket category.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Send the welcome message configured for this ticket type
        welcome_text = ticket_type["welcome_message"] or f"Welcome {interaction.user.mention}! Support staff will assist you shortly."
        welcome_text = welcome_text.replace("{user}", interaction.user.mention)
        welcome_embed = discord.Embed(
            title=f"🎫 {ticket_type_name} Ticket",
            description=welcome_text,
            color=0x3B82F6
        )
        await ticket_channel.send(embed=welcome_embed, view=TicketView(self))

        # Confirm to the user
        embed = BotEmbed.info("Ticket Created", f"Your ticket channel: {ticket_channel.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================================================================
    #  TICKET BUTTON HANDLERS (Claim, Close, Add/Remove User, Rename)
    # ================================================================
    async def claim_ticket(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ Ticket claimed by {interaction.user.mention}", ephemeral=False)

    async def close_ticket(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(embed=BotEmbed.error("Not a Ticket", ""), ephemeral=True)
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
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
    #  TICKET TYPE MANAGEMENT (admin commands)
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
        """Opens a modal to collect details for a new ticket type."""
        class AddTypeModal(discord.ui.Modal, title="Add Ticket Type"):
            name = discord.ui.TextInput(label="Name", placeholder="e.g., Support, Report, Reward Claim", required=True)
            category_id = discord.ui.TextInput(label="Category ID", placeholder="Right-click a category and copy ID", required=True)
            support_role_id = discord.ui.TextInput(label="Support Role ID", placeholder="Role ID that can manage tickets", required=False, default="0")
            welcome_message = discord.ui.TextInput(label="Welcome Message", placeholder="{user} will be replaced with the user mention", required=False, style=discord.TextStyle.paragraph, default="Welcome {user}! Staff will assist you shortly.")

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

        # The modal needs access to the cog, so we attach it
        modal = AddTypeModal()
        modal.cog = self
        await interaction.response.send_modal(modal)

    async def _remove_ticket_type_menu(self, interaction: discord.Interaction):
        """Shows a select menu with existing ticket types to remove."""
        types = await self.get_ticket_types(interaction.guild_id)
        if not types:
            embed = BotEmbed.error("No Ticket Types", "There are no ticket types to remove.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        options = []
        for t in types:
            options.append(discord.SelectOption(label=t["name"], description=f"Remove {t['name']} tickets", emoji="🗑️"))

        select_menu = discord.ui.Select(
            placeholder="Select a ticket type to remove...",
            options=options,
            custom_id="ticket_remove_select",
            min_values=1,
            max_values=1,
        )

        async def select_callback(interaction: discord.Interaction):
            selected = select_menu.values[0]
            await self.remove_ticket_type(interaction.guild_id, selected)
            embed = BotEmbed.success("Ticket Type Removed", f"**{selected}** tickets have been disabled.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            # Stop the view so the select becomes inactive
            view.stop()

        select_menu.callback = select_callback
        view = discord.ui.View(timeout=60)
        view.add_item(select_menu)
        await interaction.response.send_message("Choose a ticket type to remove:", view=view, ephemeral=True)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_types (
                guild_id INTEGER,
                name TEXT,
                category_id INTEGER,
                support_role_id INTEGER DEFAULT 0,
                welcome_message TEXT,
                PRIMARY KEY (guild_id, name)
            )
        """)
        await db.commit()
    await bot.add_cog(Ticket(bot))