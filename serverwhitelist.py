import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

WATCHED_ACTIONS = [
    "ban", "kick", "bot_add", "member_role_update",
    "channel_create", "channel_delete", "role_create", "role_delete",
    "invite_create", "member_prune", "webhook_create"
]

ACTION_CHOICES = [
    app_commands.Choice(name="All Actions (Full Bypass)", value="all"),
    app_commands.Choice(name="Ban", value="ban"),
    app_commands.Choice(name="Kick", value="kick"),
    app_commands.Choice(name="Bot-Add", value="bot_add"),
    app_commands.Choice(name="Role-Update", value="member_role_update"),
    app_commands.Choice(name="Channel-Create", value="channel_create"),
    app_commands.Choice(name="Channel-Delete", value="channel_delete"),
    app_commands.Choice(name="Role-Create", value="role_create"),
    app_commands.Choice(name="Role-Delete", value="role_delete"),
    app_commands.Choice(name="Invite-Link", value="invite_create"),
    app_commands.Choice(name="Prune", value="member_prune"),
]

# ============================================================
#  MULTI-SELECT MENU VIEW
# ============================================================
class CategorySelectView(discord.ui.View):
    def __init__(self, cog, mode, target_type, target_id, target_name):
        super().__init__(timeout=120)
        self.cog = cog
        self.mode = mode # "add" or "remove"
        self.target_type = target_type # "user", "role", or "channel"
        self.target_id = target_id
        self.target_name = target_name

        options = [discord.SelectOption(label=c.name, value=c.value) for c in ACTION_CHOICES]
        
        # Allow selecting multiple options (up to all 11)
        self.select = discord.ui.Select(
            placeholder="Select one or more categories...",
            options=options,
            min_values=1,
            max_values=len(options)
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        # We don't save yet, we wait for them to click the Confirm button
        pass

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, row=1)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        selected_values = self.select.values
        if not selected_values:
            return await interaction.response.send_message("❌ You didn't select any categories.", ephemeral=True)

        await self.cog._ensure_tables()
        table = f"sw_{self.target_type}s"
        id_col = f"{self.target_type}_id"

        async with aiosqlite.connect(DB_PATH) as db:
            if self.mode == "add":
                for cat in selected_values:
                    await db.execute(
                        f"INSERT OR REPLACE INTO {table} (guild_id, {id_col}, category) VALUES (?, ?, ?)",
                        (interaction.guild_id, self.target_id, cat)
                    )
            else:
                for cat in selected_values:
                    await db.execute(
                        f"DELETE FROM {table} WHERE guild_id = ? AND {id_col} = ? AND category = ?",
                        (interaction.guild_id, self.target_id, cat)
                    )
            await db.commit()

        action_word = "whitelisted for" if self.mode == "add" else "removed from"
        cat_text = ", ".join(selected_values)
        
        await interaction.response.edit_message(
            content=f"✅ **{self.target_name}** has been {action_word} the following categories:\n`{cat_text}`",
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
        if interaction.user.id == interaction.guild.owner_id or interaction.user.id in self.bot.owner_ids:
            return True
        await interaction.response.send_message(
            "❌ **Access Denied.** Only the Server Owner and the Bot Owner (ff5star) can manage the whitelist.", 
            ephemeral=True
        )
        return False

    wl_group = app_commands.Group(name="whitelist", description="Manage the server security whitelist")

    # ---------- ADD COMMANDS ----------
    @wl_group.command(name="add_user", description="Whitelist a user for specific actions")
    @app_commands.describe(user="User to whitelist")
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_authorized(interaction): return
        view = CategorySelectView(self, "add", "user", user.id, user.mention)
        await interaction.response.send_message(f"Select the actions {user.mention} is allowed to do:", view=view, ephemeral=True)

    @wl_group.command(name="add_role", description="Whitelist a role for specific actions")
    @app_commands.describe(role="Role to whitelist")
    async def add_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self._is_authorized(interaction): return
        view = CategorySelectView(self, "add", "role", role.id, role.mention)
        await interaction.response.send_message(f"Select the actions **{role.name}** is allowed to do:", view=view, ephemeral=True)

    @wl_group.command(name="add_channel", description="Whitelist a channel for specific actions")
    @app_commands.describe(channel="Channel to whitelist")
    async def add_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        if not await self._is_authorized(interaction): return
        view = CategorySelectView(self, "add", "channel", channel.id, channel.mention)
        await interaction.response.send_message(f"Select the actions that can happen to {channel.mention}:", view=view, ephemeral=True)

    # ---------- REMOVE COMMANDS ----------
    @wl_group.command(name="remove_user", description="Remove a user's whitelist for specific actions")
    @app_commands.describe(user="User to modify")
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_authorized(interaction): return
        view = CategorySelectView(self, "remove", "user", user.id, user.mention)
        await interaction.response.send_message(f"Select the actions to remove from {user.mention}:", view=view, ephemeral=True)

    @wl_group.command(name="remove_role", description="Remove a role's whitelist for specific actions")
    @app_commands.describe(role="Role to modify")
    async def remove_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self._is_authorized(interaction): return
        view = CategorySelectView(self, "remove", "role", role.id, role.mention)
        await interaction.response.send_message(f"Select the actions to remove from **{role.name}**:", view=view, ephemeral=True)

    @wl_group.command(name="remove_channel", description="Remove a channel from the whitelist")
    @app_commands.describe(channel="Channel to modify")
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        if not await self._is_authorized(interaction): return
        view = CategorySelectView(self, "remove", "channel", channel.id, channel.mention)
        await interaction.response.send_message(f"Select the actions to remove from {channel.mention}:", view=view, ephemeral=True)

    # ---------- VIEW COMMANDS ----------
    @wl_group.command(name="view_users", description="View all whitelisted users")
    async def view_users(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, category FROM sw_users WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message("ℹ️ No users are whitelisted.", ephemeral=True)
        lines = [f"<@{r[0]}> - `{r[1]}`" for r in rows]
        embed = discord.Embed(title="👤 Whitelisted Users", description="\n".join(lines), color=0x3B82F6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wl_group.command(name="view_roles", description="View all whitelisted roles")
    async def view_roles(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT role_id, category FROM sw_roles WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message("ℹ️ No roles are whitelisted.", ephemeral=True)
        lines = [f"<@&{r[0]}> - `{r[1]}`" for r in rows]
        embed = discord.Embed(title="🛡️ Whitelisted Roles", description="\n".join(lines), color=0x3B82F6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wl_group.command(name="view_channels", description="View all whitelisted channels")
    async def view_channels(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT channel_id, category FROM sw_channels WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message("ℹ️ No channels are whitelisted.", ephemeral=True)
        lines = [f"<#{r[0]}> - `{r[1]}`" for r in rows]
        embed = discord.Embed(title="📁 Whitelisted Channels", description="\n".join(lines), color=0x3B82F6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    #  THE STRICT KICK LOGIC
    # ============================================================
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        action_name = entry.action.name
        if action_name not in WATCHED_ACTIONS:
            return
            
        guild = entry.guild
        user = entry.user
        
        if not user or user.id == self.bot.user.id or user.id == guild.owner_id or user.id in self.bot.owner_ids:
            return
            
        await self._ensure_tables()
        
        is_whitelisted = False
        async with aiosqlite.connect(DB_PATH) as db:
            # 1. Check User Whitelist
            cursor = await db.execute("SELECT 1 FROM sw_users WHERE guild_id = ? AND user_id = ? AND (category = ? OR category = 'all')", (guild.id, user.id, action_name))
            if await cursor.fetchone():
                is_whitelisted = True
                
            # 2. Check Role Whitelist
            if not is_whitelisted:
                try:
                    member = guild.get_member(user.id) or await guild.fetch_member(user.id)
                    for role in member.roles:
                        cursor = await db.execute("SELECT 1 FROM sw_roles WHERE guild_id = ? AND role_id = ? AND (category = ? OR category = 'all')", (guild.id, role.id, action_name))
                        if await cursor.fetchone():
                            is_whitelisted = True
                            break
                except Exception:
                    pass
                        
            # 3. Check Channel Whitelist
            if not is_whitelisted and entry.target and isinstance(entry.target, discord.abc.GuildChannel):
                cursor = await db.execute("SELECT 1 FROM sw_channels WHERE guild_id = ? AND channel_id = ? AND (category = ? OR category = 'all')", (guild.id, entry.target.id, action_name))
                if await cursor.fetchone():
                    is_whitelisted = True

        # 4. Kick if not whitelisted
        if not is_whitelisted and isinstance(user, discord.Member):
            try:
                await user.kick(reason=f"Security: Unwhitelisted user attempted to use a restricted action ({action_name}).")
                
                try:
                    embed = discord.Embed(title="🚨 SECURITY KICK", description=f"**User:** {user.mention} ({user.id})\n**Action Attempted:** `{action_name}`\n**Result:** User was instantly kicked from the server.", color=discord.Color.red())
                    await guild.owner.send(embed=embed)
                except: pass
                    
            except discord.Forbidden:
                try:
                    embed = discord.Embed(title="⚠️ CRITICAL SECURITY FAILURE", description=f"Unwhitelisted user {user.mention} tried to use `{action_name}`.\n**I COULD NOT KICK THEM** because their role is higher than mine. Move my role to the top!", color=discord.Color.red())
                    await guild.owner.send(embed=embed)
                except: pass

async def setup(bot):
    await bot.add_cog(ServerWhitelist(bot))