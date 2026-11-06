import os
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from checks import is_extra_owner


def get_emoji(name: str):
    return {"tick": "✅", "cross": "❌"}.get(name)

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

WHITELIST_CATEGORIES = [
    ("channel_create", "Channel Creation"),
    ("channel_delete", "Channel Deletion"),
    ("role_create", "Role Creation"),
    ("role_delete", "Role Deletion"),
    ("ban", "Banning Members"),
    ("kick", "Kicking Members"),
    ("webhook_create", "Webhook Creation"),
    ("webhook_delete", "Webhook Deletion"),
]

TARGET_CONFIG = {
    "user": ("sw_users", "user_id"),
    "role": ("sw_roles", "role_id"),
    "channel": ("sw_channels", "channel_id")
}


class CategorySelectView(discord.ui.View):
    def __init__(self, cog, mode: str, target_type: str, target_id: int, target_name: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.mode = mode
        self.target_type = target_type
        self.target_id = target_id
        self.target_name = target_name

        options = [
            discord.SelectOption(
                label=label,
                value=cat_id,
                description=f"Allow {target_name} to do this" if mode == "add" else f"Remove permission for {target_name}"
            )
            for cat_id, label in WHITELIST_CATEGORIES
        ]

        placeholder = "Select actions to whitelist..." if mode == "add" else "Select actions to remove..."
        select = discord.ui.Select(
            placeholder=placeholder,
            min_values=1,
            max_values=len(WHITELIST_CATEGORIES),
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        await self.cog._ensure_tables()
        selected_values = interaction.data["values"]

        if self.target_type not in TARGET_CONFIG:
            await interaction.response.send_message("Invalid target type.", ephemeral=True)
            return

        table, id_col = TARGET_CONFIG[self.target_type]

        async with aiosqlite.connect(DB_PATH) as db:
            if self.mode == "add":
                for cat in selected_values:
                    if table == "sw_users":
                        await db.execute(
                            "INSERT OR REPLACE INTO sw_users (guild_id, user_id, category) VALUES (?, ?, ?)",
                            (interaction.guild_id, self.target_id, cat)
                        )
                    elif table == "sw_roles":
                        await db.execute(
                            "INSERT OR REPLACE INTO sw_roles (guild_id, role_id, category) VALUES (?, ?, ?)",
                            (interaction.guild_id, self.target_id, cat)
                        )
                    elif table == "sw_channels":
                        await db.execute(
                            "INSERT OR REPLACE INTO sw_channels (guild_id, channel_id, category) VALUES (?, ?, ?)",
                            (interaction.guild_id, self.target_id, cat)
                        )
            else:
                for cat in selected_values:
                    if table == "sw_users":
                        await db.execute(
                            "DELETE FROM sw_users WHERE guild_id = ? AND user_id = ? AND category = ?",
                            (interaction.guild_id, self.target_id, cat)
                        )
                    elif table == "sw_roles":
                        await db.execute(
                            "DELETE FROM sw_roles WHERE guild_id = ? AND role_id = ? AND category = ?",
                            (interaction.guild_id, self.target_id, cat)
                        )
                    elif table == "sw_channels":
                        await db.execute(
                            "DELETE FROM sw_channels WHERE guild_id = ? AND channel_id = ? AND category = ?",
                            (interaction.guild_id, self.target_id, cat)
                        )
            await db.commit()

        action_word = "whitelisted for" if self.mode == "add" else "removed from"
        cat_text = ", ".join(selected_values)
        tick_icon = get_emoji("tick")
        prefix = f"{tick_icon} " if tick_icon else ""

        await interaction.response.edit_message(
            content=f"{prefix}**{self.target_name}** has been {action_word} the following categories:\n`{cat_text}`",
            view=None
        )


class ServerWhitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _ensure_tables(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_users (
                guild_id INTEGER, user_id INTEGER, category TEXT, PRIMARY KEY (guild_id, user_id, category))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_roles (
                guild_id INTEGER, role_id INTEGER, category TEXT, PRIMARY KEY (guild_id, role_id, category))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_channels (
                guild_id INTEGER, channel_id INTEGER, category TEXT, PRIMARY KEY (guild_id, channel_id, category))""")
            await db.commit()

    async def _is_authorized(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if interaction.user.id == interaction.guild.owner_id or interaction.user.id in self.bot.owner_ids:
            return True
        if await is_extra_owner(interaction.guild.id, interaction.user.id):
            return True
        cross_icon = get_emoji("cross")
        prefix = f"{cross_icon} " if cross_icon else ""
        await interaction.response.send_message(
            f"{prefix}**Access Denied.** Only the Server Owner, Extra Owners, and Bot Owners can manage the whitelist.",
            ephemeral=True
        )
        return False

    wl_group = app_commands.Group(name="whitelist", description="Manage the server security whitelist")

    @wl_group.command(name="add_user", description="Whitelist a user for specific actions")
    @app_commands.describe(user="User to whitelist")
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        view = CategorySelectView(self, "add", "user", user.id, user.mention)
        await interaction.response.send_message(f"Choose actions {user.mention} is allowed to perform:", view=view, ephemeral=True)

    @wl_group.command(name="add_role", description="Whitelist a role for specific actions")
    @app_commands.describe(role="Role to whitelist")
    async def add_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        view = CategorySelectView(self, "add", "role", role.id, role.mention)
        await interaction.response.send_message(f"Choose actions **{role.name}** is allowed to perform:", view=view, ephemeral=True)

    @wl_group.command(name="add_channel", description="Whitelist a channel for specific actions")
    @app_commands.describe(channel="Channel to whitelist")
    async def add_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        view = CategorySelectView(self, "add", "channel", channel.id, channel.mention)
        await interaction.response.send_message(f"Choose actions that can affect {channel.mention}:", view=view, ephemeral=True)

    @wl_group.command(name="remove_user", description="Remove a user's whitelist for specific actions")
    @app_commands.describe(user="User to modify")
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        view = CategorySelectView(self, "remove", "user", user.id, user.mention)
        await interaction.response.send_message(f"Choose actions to revoke for {user.mention}:", view=view, ephemeral=True)

    @wl_group.command(name="remove_role", description="Remove a role's whitelist for specific actions")
    @app_commands.describe(role="Role to modify")
    async def remove_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        view = CategorySelectView(self, "remove", "role", role.id, role.mention)
        await interaction.response.send_message(f"Choose actions to revoke for **{role.name}**:", view=view, ephemeral=True)

    @wl_group.command(name="remove_channel", description="Remove a channel from the whitelist")
    @app_commands.describe(channel="Channel to modify")
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        view = CategorySelectView(self, "remove", "channel", channel.id, channel.mention)
        await interaction.response.send_message(f"Choose actions to revoke for {channel.mention}:", view=view, ephemeral=True)

    @wl_group.command(name="view_users", description="View all whitelisted users")
    async def view_users(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT user_id, category FROM sw_users WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message("No users are currently whitelisted.", ephemeral=True)

        user_map: dict[int, list[str]] = {}
        for r in rows:
            user_map.setdefault(r["user_id"], []).append(r["category"])

        embed = discord.Embed(title="Whitelisted Users", color=0x3B82F6)
        for uid, cats in user_map.items():
            member = interaction.guild.get_member(uid)
            name = member.mention if member else f"User ID `{uid}`"
            embed.add_field(name=f"👤 {name}", value=", ".join(cats), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wl_group.command(name="view_roles", description="View all whitelisted roles")
    async def view_roles(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT role_id, category FROM sw_roles WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message("No roles are currently whitelisted.", ephemeral=True)

        role_map: dict[int, list[str]] = {}
        for r in rows:
            role_map.setdefault(r["role_id"], []).append(r["category"])

        embed = discord.Embed(title="Whitelisted Roles", color=0x3B82F6)
        for rid, cats in role_map.items():
            role = interaction.guild.get_role(rid)
            name = role.mention if role else f"Role ID `{rid}`"
            embed.add_field(name=f"🔰 {name}", value=", ".join(cats), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wl_group.command(name="view_channels", description="View all whitelisted channels")
    async def view_channels(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction):
            return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT channel_id, category FROM sw_channels WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message("No channels are currently whitelisted.", ephemeral=True)

        channel_map: dict[int, list[str]] = {}
        for r in rows:
            channel_map.setdefault(r["channel_id"], []).append(r["category"])

        embed = discord.Embed(title="Whitelisted Channels", color=0x3B82F6)
        for cid, cats in channel_map.items():
            channel = interaction.guild.get_channel(cid)
            name = channel.mention if channel else f"Channel ID `{cid}`"
            embed.add_field(name=f"📁 {name}", value=", ".join(cats), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    cog = ServerWhitelist(bot)
    await cog._ensure_tables()
    await bot.add_cog(cog)
