import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import asyncio

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# All monitored actions
WATCHED_ACTIONS = [
    "ban", "kick", "bot_add", "member_role_update",
    "channel_create", "channel_delete", "role_create", "role_delete",
    "invite_create", "member_prune", "webhook_create"
]

# The dropdown options you will see in Discord
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

class ServerWhitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================================
    #  LAZY TABLE CREATION
    # ============================================================
    async def _ensure_tables(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_users (
                guild_id INTEGER, user_id INTEGER, category TEXT, PRIMARY KEY (guild_id, user_id, category))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_roles (
                guild_id INTEGER, role_id INTEGER, category TEXT, PRIMARY KEY (guild_id, role_id, category))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_channels (
                guild_id INTEGER, channel_id INTEGER, category TEXT, PRIMARY KEY (guild_id, channel_id, category))""")
            await db.commit()

    # ============================================================
    #  PERMISSION CHECK (ONLY YOU AND SERVER OWNER)
    # ============================================================
    async def _is_authorized(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id or interaction.user.id in self.bot.owner_ids:
            return True
        await interaction.response.send_message(
            "❌ **Access Denied.** Only the Server Owner and the Bot Owner (ff5star) can manage the whitelist.", 
            ephemeral=True
        )
        return False

    # ============================================================
    #  COMMAND GROUP: /whitelist
    # ============================================================
    wl_group = app_commands.Group(name="whitelist", description="Manage the server security whitelist")

    # ---------- ADD COMMANDS ----------
    @wl_group.command(name="add_user", description="Whitelist a user for a specific action")
    @app_commands.describe(user="User to whitelist", category="What action can they perform?")
    @app_commands.choices(category=ACTION_CHOICES)
    async def add_user(self, interaction: discord.Interaction, user: discord.Member, category: str):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO sw_users (guild_id, user_id, category) VALUES (?, ?, ?)", (interaction.guild_id, user.id, category))
            await db.commit()
        cat_name = next((c.name for c in ACTION_CHOICES if c.value == category), category)
        await interaction.response.send_message(f"✅ {user.mention} has been whitelisted for **{cat_name}**.", ephemeral=True)

    @wl_group.command(name="add_role", description="Whitelist a role for a specific action")
    @app_commands.describe(role="Role to whitelist", category="What action can they perform?")
    @app_commands.choices(category=ACTION_CHOICES)
    async def add_role(self, interaction: discord.Interaction, role: discord.Role, category: str):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO sw_roles (guild_id, role_id, category) VALUES (?, ?, ?)", (interaction.guild_id, role.id, category))
            await db.commit()
        cat_name = next((c.name for c in ACTION_CHOICES if c.value == category), category)
        await interaction.response.send_message(f"✅ The role **{role.name}** has been whitelisted for **{cat_name}**.", ephemeral=True)

    @wl_group.command(name="add_channel", description="Whitelist a channel for a specific action")
    @app_commands.describe(channel="Channel to whitelist", category="What action can happen to this channel?")
    @app_commands.choices(category=ACTION_CHOICES)
    async def add_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel, category: str):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO sw_channels (guild_id, channel_id, category) VALUES (?, ?, ?)", (interaction.guild_id, channel.id, category))
            await db.commit()
        cat_name = next((c.name for c in ACTION_CHOICES if c.value == category), category)
        await interaction.response.send_message(f"✅ The channel {channel.mention} has been whitelisted for **{cat_name}**.", ephemeral=True)

    # ---------- REMOVE COMMANDS ----------
    @wl_group.command(name="remove_user", description="Remove a user's whitelist for an action")
    @app_commands.describe(user="User to modify", category="The action to remove")
    @app_commands.choices(category=ACTION_CHOICES)
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member, category: str):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sw_users WHERE guild_id = ? AND user_id = ? AND category = ?", (interaction.guild_id, user.id, category))
            await db.commit()
        await interaction.response.send_message(f"🗑️ {user.mention} is no longer whitelisted for that action.", ephemeral=True)

    @wl_group.command(name="remove_role", description="Remove a role's whitelist for an action")
    @app_commands.describe(role="Role to modify", category="The action to remove")
    @app_commands.choices(category=ACTION_CHOICES)
    async def remove_role(self, interaction: discord.Interaction, role: discord.Role, category: str):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sw_roles WHERE guild_id = ? AND role_id = ? AND category = ?", (interaction.guild_id, role.id, category))
            await db.commit()
        await interaction.response.send_message(f"🗑️ The role **{role.name}** is no longer whitelisted for that action.", ephemeral=True)

    @wl_group.command(name="remove_channel", description="Remove a channel from the whitelist")
    @app_commands.describe(channel="Channel to modify", category="The action to remove")
    @app_commands.choices(category=ACTION_CHOICES)
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel, category: str):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sw_channels WHERE guild_id = ? AND channel_id = ? AND category = ?", (interaction.guild_id, channel.id, category))
            await db.commit()
        await interaction.response.send_message(f"🗑️ The channel {channel.mention} is no longer whitelisted for that action.", ephemeral=True)

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
            # 1. Check User Whitelist (for this action OR 'all')
            cursor = await db.execute(
                "SELECT 1 FROM sw_users WHERE guild_id = ? AND user_id = ? AND (category = ? OR category = 'all')", 
                (guild.id, user.id, action_name)
            )
            if await cursor.fetchone():
                is_whitelisted = True
                
            # 2. Check Role Whitelist (for this action OR 'all')
            if not is_whitelisted and isinstance(user, discord.Member):
                for role in user.roles:
                    cursor = await db.execute(
                        "SELECT 1 FROM sw_roles WHERE guild_id = ? AND role_id = ? AND (category = ? OR category = 'all')", 
                        (guild.id, role.id, action_name)
                    )
                    if await cursor.fetchone():
                        is_whitelisted = True
                        break
                        
            # 3. Check Channel Whitelist (e.g. if someone is trying to delete a whitelisted channel)
            if not is_whitelisted and entry.target and isinstance(entry.target, discord.abc.GuildChannel):
                cursor = await db.execute(
                    "SELECT 1 FROM sw_channels WHERE guild_id = ? AND channel_id = ? AND (category = ? OR category = 'all')", 
                    (guild.id, entry.target.id, action_name)
                )
                if await cursor.fetchone():
                    is_whitelisted = True

        # 4. If not whitelisted, KICK THEM
        if not is_whitelisted and isinstance(user, discord.Member):
            try:
                await user.kick(reason=f"Security: Unwhitelisted user attempted to use a restricted action ({action_name}).")
                
                try:
                    embed = discord.Embed(
                        title="🚨 SECURITY KICK",
                        description=f"**User:** {user.mention} ({user.id})\n**Action Attempted:** `{action_name}`\n**Result:** User was instantly kicked from the server.",
                        color=discord.Color.red()
                    )
                    await guild.owner.send(embed=embed)
                except:
                    pass
                    
            except discord.Forbidden:
                try:
                    embed = discord.Embed(
                        title="⚠️ CRITICAL SECURITY FAILURE",
                        description=f"Unwhitelisted user {user.mention} tried to use `{action_name}`.\n**I COULD NOT KICK THEM** because their role is higher than mine. Move my role to the top!",
                        color=discord.Color.red()
                    )
                    await guild.owner.send(embed=embed)
                except:
                    pass

async def setup(bot):
    await bot.add_cog(ServerWhitelist(bot))