import sqlite3
import os
from datetime import datetime, timezone
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from dotenv import load_dotenv

load_dotenv()
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")

app = Flask(__name__)

# ----- Database helpers -----
def get_db():
    return sqlite3.connect(DATABASE_PATH)

def get_antinuke_status(guild_id):
    conn = get_db()
    cursor = conn.execute("SELECT antinuke_enabled FROM guild_settings WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 1

def get_recent_logs(guild_id, limit=20):
    conn = get_db()
    cursor = conn.execute(
        "SELECT timestamp, user_id, event_type, punishment FROM antinuke_logs WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
        (guild_id, limit),
    )
    logs = cursor.fetchall()
    conn.close()
    return logs

def format_time(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return ts

# ----- Your existing HTML templates (keep them as they are) -----
LANDING_HTML = """
... (your big HTML here, unchanged)
"""

DASHBOARD_HTML = """
... (your dashboard HTML here, unchanged)
"""

# ----- Routes -----
@app.route("/")
def landing():
    bot = app.config.get("bot")
    if not bot: return "Bot still starting up.", 503
    guild_count = len(bot.guilds)
    bot_avatar = bot.user.display_avatar.url
    return render_template_string(LANDING_HTML, bot_avatar=bot_avatar, guild_count=guild_count)

@app.route("/dashboard")
def dashboard():
    bot = app.config.get("bot")
    if not bot: return "Bot not initialized.", 500
    all_guilds = sorted(bot.guilds, key=lambda g: g.name.lower())
    guild_id = request.args.get("guild_id", type=int)
    if not guild_id and all_guilds: guild_id = all_guilds[0].id
    guild_count = len(all_guilds)
    antinuke_enabled = get_antinuke_status(guild_id) if guild_id else None
    logs = get_recent_logs(guild_id) if guild_id else []
    logs = [(format_time(row[0]), row[1], row[2], row[3]) for row in logs]
    bot_avatar = bot.user.display_avatar.url
    return render_template_string(DASHBOARD_HTML,
                                  guild_id=guild_id,
                                  all_guilds=[{"id": g.id, "name": g.name, "member_count": g.member_count} for g in all_guilds],
                                  guild_count=guild_count,
                                  antinuke_enabled=antinuke_enabled,
                                  logs=logs,
                                  bot_avatar=bot_avatar)

@app.route("/toggle")
def toggle():
    guild_id = request.args.get("guild_id", type=int)
    if not guild_id: return "Missing guild_id", 400
    new_val = 0 if get_antinuke_status(guild_id) else 1
    conn = get_db()
    conn.execute("UPDATE guild_settings SET antinuke_enabled = ? WHERE guild_id = ?", (new_val, guild_id))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard", guild_id=guild_id))

@app.route("/logs")
def view_logs():
    guild_id = request.args.get("guild_id", type=int)
    logs = get_recent_logs(guild_id, 50)
    return jsonify([dict(zip(["timestamp", "user_id", "event_type", "punishment"], row)) for row in logs])

# ----- API (now inside the same app) -----
@app.route("/api/stats")
def api_stats():
    bot = app.config.get("bot")
    if not bot: return jsonify({"error": "Bot not initialized"}), 503
    return jsonify({
        "bot_name": str(bot.user), "bot_id": bot.user.id,
        "bot_avatar": str(bot.user.display_avatar.url),
        "guild_count": len(bot.guilds),
        "user_count": sum(g.member_count for g in bot.guilds),
        "latency_ms": round(bot.latency * 1000, 2),
        "commands": 65, "version": "2.0.0",
        "invite_url": "https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473370870&integration_type=0&scope=bot+applications.commands"
    })

@app.route("/api/invite")
def api_invite():
    return jsonify({"invite_url": "https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473370870&integration_type=0&scope=bot+applications.commands"})

@app.route("/api/guild/<int:guild_id>")
def api_guild(guild_id):
    bot = app.config.get("bot")
    if not bot: return jsonify({"error": "Bot not initialized"}), 503
    guild = bot.get_guild(guild_id)
    if not guild: return jsonify({"error": "Guild not found"}), 404
    conn = get_db()
    cursor = conn.execute("SELECT antinuke_enabled FROM guild_settings WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    antinuke = bool(row[0]) if row else False
    conn.close()
    return jsonify({"name": guild.name, "id": guild.id, "member_count": guild.member_count,
                    "owner_id": guild.owner_id, "antinuke_enabled": antinuke})

@app.route("/api/leaderboard")
def api_leaderboard():
    bot = app.config.get("bot")
    if not bot: return jsonify({"error": "Bot not initialized"}), 503
    guilds = sorted(bot.guilds, key=lambda g: g.member_count, reverse=True)[:10]
    return jsonify([{"name": g.name, "members": g.member_count, "id": g.id} for g in guilds])

@app.route("/api/guilds")
def api_guilds():
    bot = app.config.get("bot")
    if not bot: return jsonify({"error": "Bot not initialized"}), 503
    return jsonify([{"name": g.name, "id": g.id, "member_count": g.member_count} for g in bot.guilds])