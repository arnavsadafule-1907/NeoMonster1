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

    async def get_ticket_settings(self, guild_id: int, ticket_type: str):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM ticket_settings WHERE guild_id = ? AND ticket_type = ?",
                (guild_id, ticket_type)
            )
            row = await cursor.fetchone()
            if row:
                return {"category_id": row["category_id"], "support_role_id": row["support_role_id"]}
            return None

    async def set_ticket_settings(self, guild_id, ticket_type, category_id, support_role_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ticket_settings (guild_id, ticket_type, category_id, support_role_id) VALUES (?, ?, ?, ?)",
                (guild_id, ticket_type, category_id, support_role_id)
            )
            await db.commit()

    # ---------- Slash: /ticket (open a ticket) ----------
    @app_commands.command(name="ticket", description="Open a support ticket")
    @app_commands.describe(ticket_type="Type of ticket")
    @app_commands.choices(ticket_type=[
        app_commands.Choice(name="Support", value="support"),
        app_commands.Choice(name="Reward Claim", value="reward"),
        app_commands.Choice(name="Report", value="report"),
        app_commands.Choice(name="Other", value="other"),
    ])
    async def ticket_open(self, interaction: discord.Interaction, ticket_type: str):
        settings = await self.get_ticket_settings(interaction.guild_id, ticket_type)
        if not settings or not settings["category_id"]:
            embed = BotEmbed.error("Tickets Disabled", f"No configuration for `{ticket_type}` tickets. Ask an admin to use `/ticketsetup`.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        category = interaction.guild.get_channel(settings["category_id"])
        if not category:
            embed = BotEmbed.error("Invalid Category", "The ticket category no longer exists.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_name = f"ticket-{interaction.user.name}-{ticket_type}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        if settings["support_role_id"]:
            role = interaction.guild.get_role(settings["support_role_id"])
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ticket_channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Ticket created by {interaction.user}"
            )
        except discord.Forbidden:
            embed = BotEmbed.error("Permission Denied", "I need `Manage Channels` in the ticket category.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = BotEmbed.info("Ticket Created", f"Your ticket channel: {ticket_channel.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        panel_embed = discord.Embed(
            title=f"🎫 {ticket_type.capitalize()} Ticket",
            description=f"Welcome {interaction.user.mention}! Support staff will assist you shortly.",
            color=0x3B82F6
        )
        await ticket_channel.send(embed=panel_embed, view=TicketView(self))

    # ---------- Button handlers ----------
    async def claim_ticket(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ Ticket claimed by {interaction.user.mention}", ephemeral=False)

    async def close_ticket(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket closed")

    async def add_user_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddUserModal(self, interaction.channel))

    async def remove_user_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RemoveUserModal(self, interaction.channel))

    async def rename_ticket_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RenameTicketModal(self, interaction.channel))

    # ---------- Staff slash commands ----------
    @app_commands.command(name="ticket-add", description="Add a user to the current ticket")
    @app_commands.describe(user="User to add")
    @admin_only()
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            embed = BotEmbed.error("Not a Ticket", "This command can only be used in a ticket channel.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
        await interaction.response.send_message(embed=BotEmbed.success("User Added", f"{user.mention} can now see this ticket."))

    @app_commands.command(name="ticket-remove", description="Remove a user from the current ticket")
    @app_commands.describe(user="User to remove")
    @admin_only()
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            embed = BotEmbed.error("Not a Ticket", "This command can only be used in a ticket channel.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=BotEmbed.success("User Removed", f"{user.mention} has been removed."))

    @app_commands.command(name="ticket-rename", description="Rename the current ticket")
    @app_commands.describe(name="New name (e.g., billing-issue)")
    @admin_only()
    async def ticket_rename(self, interaction: discord.Interaction, name: str):
        if not interaction.channel.name.startswith("ticket-"):
            embed = BotEmbed.error("Not a Ticket", "This command can only be used in a ticket channel.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        new_name = name.replace(" ", "-").lower()
        await interaction.channel.edit(name=f"ticket-{new_name}")
        await interaction.response.send_message(embed=BotEmbed.success("Renamed", f"Ticket renamed to `{new_name}`."))

    @app_commands.command(name="ticket-close", description="Close the current ticket")
    @admin_only()
    async def ticket_close_slash(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            embed = BotEmbed.error("Not a Ticket", "This command can only be used in a ticket channel.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket closed")

    @app_commands.command(name="ticket-claim", description="Claim the current ticket")
    @admin_only()
    async def ticket_claim_slash(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            embed = BotEmbed.error("Not a Ticket", "This command can only be used in a ticket channel.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await interaction.response.send_message(embed=BotEmbed.success("Claimed", f"Ticket claimed by {interaction.user.mention}."))

    # ---------- Setup command ----------
    @app_commands.command(name="ticketsetup", description="Configure a ticket type")
    @app_commands.describe(
        ticket_type="Type of ticket to configure",
        category="Category where ticket channels are created",
        support_role="Role that can manage tickets"
    )
    @app_commands.choices(ticket_type=[
        app_commands.Choice(name="Support", value="support"),
        app_commands.Choice(name="Reward Claim", value="reward"),
        app_commands.Choice(name="Report", value="report"),
        app_commands.Choice(name="Other", value="other"),
    ])
    @admin_only()
    async def ticketsetup(self, interaction: discord.Interaction, ticket_type: str, category: discord.CategoryChannel, support_role: discord.Role):
        await self.set_ticket_settings(interaction.guild_id, ticket_type, category.id, support_role.id)
        embed = BotEmbed.success("Ticket System Configured",
                                 f"**Type:** `{ticket_type}`\n**Category:** {category.mention}\n**Support Role:** {support_role.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_settings (
                guild_id INTEGER,
                ticket_type TEXT,
                category_id INTEGER,
                support_role_id INTEGER,
                PRIMARY KEY (guild_id, ticket_type)
            )
        """)
        await db.commit()
    await bot.add_cog(Ticket(bot))