from flask import Flask, jsonify, request
import os
from dotenv import load_dotenv
import sqlite3

load_dotenv()
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

api_app = Flask(__name__)

@api_app.route("/api/stats")
def api_stats():
    bot = api_app.config.get("bot")
    if not bot:
        return jsonify({"error": "Bot not initialized"}), 503

    return jsonify({
        "bot_name": str(bot.user),
        "bot_id": bot.user.id,
        "bot_avatar": str(bot.user.display_avatar.url),
        "guild_count": len(bot.guilds),
        "user_count": sum(g.member_count for g in bot.guilds),
        "uptime": "Online",
        "latency_ms": round(bot.latency * 1000, 2),
        "commands": 100,
        "version": "2.0.0",
        "invite_url": "https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473378998&integration_type=0&scope=bot+applications.commands"
    })

@api_app.route("/api/invite")
def api_invite():
    return jsonify({
        "invite_url": "https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473378998&integration_type=0&scope=bot+applications.commands"
    })

@api_app.route("/api/guild/<int:guild_id>")
def api_guild(guild_id):
    bot = api_app.config.get("bot")
    if not bot:
        return jsonify({"error": "Bot not initialized"}), 503

    guild = bot.get_guild(guild_id)
    if not guild:
        return jsonify({"error": "Guild not found"}), 404

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.execute("SELECT antinuke_enabled FROM guild_settings WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    antinuke = bool(row[0]) if row else False
    conn.close()

    return jsonify({
        "name": guild.name,
        "id": guild.id,
        "member_count": guild.member_count,
        "owner_id": guild.owner_id,
        "icon_url": str(guild.icon.url) if guild.icon else None,
        "antinuke_enabled": antinuke
    })

@api_app.route("/api/leaderboard")
def api_leaderboard():
    bot = api_app.config.get("bot")
    if not bot:
        return jsonify({"error": "Bot not initialized"}), 503
    guilds = sorted(bot.guilds, key=lambda g: g.member_count, reverse=True)[:10]
    return jsonify([{
        "name": g.name,
        "members": g.member_count,
        "id": g.id,
        "icon_url": str(g.icon.url) if g.icon else None
    } for g in guilds])

@api_app.route("/api/guilds")
def api_guilds():
    bot = api_app.config.get("bot")
    if not bot:
        return jsonify({"error": "Bot not initialized"}), 503
    return jsonify([{
        "name": g.name,
        "id": g.id,
        "member_count": g.member_count
    } for g in bot.guilds])

def start_api(bot):
    api_app.config["bot"] = bot
    from threading import Thread
    thread = Thread(target=api_app.run, kwargs={"host": "0.0.0.0", "port": 5001, "debug": False, "use_reloader": False}, daemon=True)
    thread.start()