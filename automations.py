import discord
from discord import app_commands
from discord.ext import commands, tasks
from checks import admin_only
from formatter import BotEmbed

class Automations(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduled_messages = []

    @app_commands.command(name="auto", description="Automation tasks")
    @app_commands.describe(action="Action", role="Role for auto role", channel="Channel for scheduled message", message="Message text", interval="Interval in minutes")
    @app_commands.choices(action=[
        app_commands.Choice(name="role add", value="role_add"),
        app_commands.Choice(name="role remove", value="role_remove"),
        app_commands.Choice(name="message add", value="msg_add"),
        app_commands.Choice(name="message remove", value="msg_remove"),
    ])
    @admin_only()
    async def auto(self, interaction: discord.Interaction, action: str, role: discord.Role = None, channel: discord.TextChannel = None, message: str = None, interval: int = None):
        if action in ["role_add", "role_remove"]:
            embed = BotEmbed.info("Auto Role", "Auto role is managed via /welcome role. Use that command.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        elif action == "msg_add":
            if not channel or not message or not interval:
                embed = BotEmbed.error("Missing Parameters", "Provide channel, message, and interval.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            @tasks.loop(minutes=interval)
            async def scheduled_task():
                await channel.send(message)
            scheduled_task.start()
            self.scheduled_messages.append({"task": scheduled_task})
            embed = BotEmbed.success("Scheduled Message", f"Message will be sent every {interval} minutes in {channel.mention}.")
        elif action == "msg_remove":
            if self.scheduled_messages:
                self.scheduled_messages[-1]["task"].cancel()
                self.scheduled_messages.pop()
                embed = BotEmbed.success("Removed", "Last scheduled message removed.")
            else:
                embed = BotEmbed.error("None", "No scheduled messages to remove.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def cog_unload(self):
        for entry in self.scheduled_messages:
            entry["task"].cancel()

async def setup(bot):
    await bot.add_cog(Automations(bot))