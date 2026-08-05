import discord
from discord import app_commands
from discord.ext import commands
import secrets
import os
from formatter import BotEmbed

RECOVERY_FILE = "./data/recovery_keys.txt"

class OwnerRecovery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("./data", exist_ok=True)

    @app_commands.command(name="generaterecovery", description="Generate a one‑time recovery key (owner only)")
    async def generate_recovery(self, interaction: discord.Interaction):
        if interaction.user.id not in self.bot.owner_ids:
            embed = BotEmbed.error("Permission Denied", "Only the bot owner can generate recovery keys.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        key = secrets.token_hex(16)
        with open(RECOVERY_FILE, "a") as f:
            f.write(f"{key}\n")

        embed = BotEmbed.success("Recovery Key Generated", f"```\n{key}\n```\nKeep this safe! It can be used ONCE to regain owner access.")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="recoverowner", description="Use a recovery key to become server owner")
    @app_commands.describe(key="Your one‑time recovery key")
    async def recover_owner(self, interaction: discord.Interaction, key: str):
        if not os.path.exists(RECOVERY_FILE):
            embed = BotEmbed.error("No Keys", "No recovery keys have been generated.")
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        with open(RECOVERY_FILE, "r") as f:
            keys = f.readlines()

        if key + "\n" in keys:
            # Remove the used key
            keys.remove(key + "\n")
            with open(RECOVERY_FILE, "w") as f:
                f.writelines(keys)

            # Transfer ownership
            try:
                await interaction.guild.edit(owner=interaction.user)
                embed = BotEmbed.success("Ownership Transferred", f"{interaction.user.mention} is now the server owner!")
            except discord.Forbidden:
                embed = BotEmbed.error("Failed", "I cannot transfer ownership. Ensure I have Administrator permissions.")
            except Exception as e:
                embed = BotEmbed.error("Error", str(e))
        else:
            embed = BotEmbed.error("Invalid Key", "That recovery key is invalid or has already been used.")

        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot):
    await bot.add_cog(OwnerRecovery(bot))