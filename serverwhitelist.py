import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import asyncio

DB_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

# The specific actions you want to monitor
WATCHED_ACTIONS = [
    discord.AuditLogAction.ban,
    discord.AuditLogAction.kick,
    discord.AuditLogAction.bot_add,
    discord.AuditLogAction.member_role_update,
    discord.AuditLogAction.channel_create,
    discord.AuditLogAction.channel_delete,
    discord.AuditLogAction.role_create,
    discord.AuditLogAction.role_delete,
    discord.AuditLogAction.invite_create,
    discord.AuditLogAction.member_prune
]

class ServerWhitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================================
    #  LAZY TABLE CREATION (Prevents data loss on Render restart)
    # ============================================================
    async def _ensure_tables(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_users (
                guild_id INTEGER, user_id INTEGER, PRIMARY KEY (guild_id, user_id))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_roles (
                guild_id INTEGER, role_id INTEGER, PRIMARY KEY (guild_id, role_id))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS sw_channels (
                guild_id INTEGER, channel_id INTEGER, PRIMARY KEY (guild_id, channel_id))""")
            await db.commit()

    # ============================================================
    #  PERMISSION CHECK (Only Bot Owner & Server Owner)
    # ============================================================
    async def _is_authorized(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id or interaction.user.id in self.bot.owner_ids:
            return True
        await interaction.response.send_message(
            "❌ **Access Denied.** Only the Server Owner or Bot Owner can manage the whitelist.", 
            ephemeral=True
        )
        return False

    # ============================================================
    #  COMMAND GROUP: /whitelist
    # ============================================================
    wl_group = app_commands.Group(name="whitelist", description="Manage the server security whitelist")

    # ---------- ADD COMMANDS ----------
    @wl_group.command(name="add_user", description="Whitelist a user so they don't get kicked")
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO sw_users (guild_id, user_id) VALUES (?, ?)", (interaction.guild_id, user.id))
            await db.commit()
        await interaction.response.send_message(f"✅ {user.mention} has been whitelisted.", ephemeral=True)

    @wl_group.command(name="add_role", description="Whitelist a role so its members don't get kicked")
    async def add_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO sw_roles (guild_id, role_id) VALUES (?, ?)", (interaction.guild_id, role.id))
            await db.commit()
        await interaction.response.send_message(f"✅ The role **{role.name}** has been whitelisted.", ephemeral=True)

    @wl_group.command(name="add_channel", description="Whitelist a channel (prevents deletion)")
    async def add_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO sw_channels (guild_id, channel_id) VALUES (?, ?)", (interaction.guild_id, channel.id))
            await db.commit()
        await interaction.response.send_message(f"✅ The channel {channel.mention} has been whitelisted.", ephemeral=True)

    # ---------- REMOVE COMMANDS ----------
    @wl_group.command(name="remove_user", description="Remove a user from the whitelist")
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sw_users WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, user.id))
            await db.commit()
        await interaction.response.send_message(f"🗑️ {user.mention} has been removed from the whitelist.", ephemeral=True)

    @wl_group.command(name="remove_role", description="Remove a role from the whitelist")
    async def remove_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sw_roles WHERE guild_id = ? AND role_id = ?", (interaction.guild_id, role.id))
            await db.commit()
        await interaction.response.send_message(f"🗑️ The role **{role.name}** has been removed from the whitelist.", ephemeral=True)

    @wl_group.command(name="remove_channel", description="Remove a channel from the whitelist")
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sw_channels WHERE guild_id = ? AND channel_id = ?", (interaction.guild_id, channel.id))
            await db.commit()
        await interaction.response.send_message(f"🗑️ The channel {channel.mention} has been removed from the whitelist.", ephemeral=True)

    # ---------- VIEW COMMANDS ----------
    @wl_group.command(name="view_users", description="View all whitelisted users")
    async def view_users(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id FROM sw_users WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message("ℹ️ No users are whitelisted.", ephemeral=True)
            
        mentions = [f"<@{r[0]}>" for r in rows]
        embed = discord.Embed(title="👤 Whitelisted Users", description="\n".join(mentions), color=0x3B82F6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wl_group.command(name="view_roles", description="View all whitelisted roles")
    async def view_roles(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT role_id FROM sw_roles WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message("ℹ️ No roles are whitelisted.", ephemeral=True)
            
        mentions = [f"<@&{r[0]}>" for r in rows]
        embed = discord.Embed(title="🛡️ Whitelisted Roles", description="\n".join(mentions), color=0x3B82F6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wl_group.command(name="view_channels", description="View all whitelisted channels")
    async def view_channels(self, interaction: discord.Interaction):
        if not await self._is_authorized(interaction): return
        await self._ensure_tables()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT channel_id FROM sw_channels WHERE guild_id = ?", (interaction.guild_id,))
            rows = await cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message("ℹ️ No channels are whitelisted.", ephemeral=True)
            
        mentions = [f"<#{r[0]}>" for r in rows]
        embed = discord.Embed(title="📁 Whitelisted Channels", description="\n".join(mentions), color=0x3B82F6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    #  THE KICK LOGIC (Audit Logs)
    # ============================================================
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        # 1. Only check watched actions
        if entry.action not in WATCHED_ACTIONS:
            return
            
        guild = entry.guild
        user = entry.user
        
        # 2. Ignore if it's the bot itself, the server owner, or the bot owner
        if user.id == self.bot.user.id or user.id == guild.owner_id or user.id in self.bot.owner_ids:
            return
            
        await self._ensure_tables()
        
        # 3. Check database for whitelist
        is_whitelisted = False
        async with aiosqlite.connect(DB_PATH) as db:
            # Check User Whitelist
            cursor = await db.execute("SELECT 1 FROM sw_users WHERE guild_id = ? AND user_id = ?", (guild.id, user.id))
            if await cursor.fetchone():
                is_whitelisted = True
                
            # Check Role Whitelist
            if not is_whitelisted and isinstance(user, discord.Member):
                for role in user.roles:
                    cursor = await db.execute("SELECT 1 FROM sw_roles WHERE guild_id = ? AND role_id = ?", (guild.id, role.id))
                    if await cursor.fetchone():
                        is_whitelisted = True
                        break
                        
            # Check Channel Whitelist (for channel deletions)
            if not is_whitelisted and entry.action in [discord.AuditLogAction.channel_delete, discord.AuditLogAction.channel_create]:
                if entry.target:
                    cursor = await db.execute("SELECT 1 FROM sw_channels WHERE guild_id = ? AND channel_id = ?", (guild.id, entry.target.id))
                    if await cursor.fetchone():
                        is_whitelisted = True

        # 4. If not whitelisted, KICK THEM
        if not is_whitelisted and isinstance(user, discord.Member):
            try:
                # We try to kick them. If their role is higher than the bot, this fails silently.
                await user.kick(reason=f"Security: Unwhitelisted user attempted to use a restricted action ({entry.action.name}).")
                
                # Alert the server owner
                try:
                    embed = discord.Embed(
                        title="🚨 Unwhitelisted Action Blocked",
                        description=f"**User:** {user.mention} ({user.id})\n**Action:** `{entry.action.name}`\n**Result:** Kicked from server.",
                        color=discord.Color.red()
                    )
                    await guild.owner.send(embed=embed)
                except:
                    pass
                    
            except discord.Forbidden:
                # If the bot can't kick them (because their role is too high), log it to console
                print(f"⚠️ Failed to kick {user.name} - They have a higher role than the bot.")

async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS sw_users (guild_id INTEGER, user_id INTEGER, PRIMARY KEY (guild_id, user_id))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS sw_roles (guild_id INTEGER, role_id INTEGER, PRIMARY KEY (guild_id, role_id))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS sw_channels (guild_id INTEGER, channel_id INTEGER, PRIMARY KEY (guild_id, channel_id))""")
        await db.commit()
    await bot.add_cog(ServerWhitelist(bot))