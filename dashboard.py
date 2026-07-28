import sqlite3
import os
import secrets
from datetime import datetime, timezone
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from dotenv import load_dotenv
import requests

load_dotenv()
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY or secrets.token_hex(32)

# ---------- Database helpers ----------
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

# ---------- Discord OAuth ----------
def get_oauth_url():
    return f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri=https%3A%2F%2Fneomonster1-production.up.railway.app%2Fcallback&response_type=code&scope=identify+guilds"

def exchange_code(code):
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'https://neomonster1-production.up.railway.app/callback'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
    r.raise_for_status()
    return r.json()

def get_user_guilds(token):
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
    r.raise_for_status()
    guilds = r.json()
    # Keep only servers where the user is OWNER (or has ADMINISTRATOR permission)
    user_guilds = []
    for g in guilds:
        if g['owner'] or (int(g['permissions']) & 0x8):
            user_guilds.append(g)
    return user_guilds

# ---------- HTML templates (keep your existing LANDING_HTML unchanged) ----------
LANDING_HTML = """ ... """   # (your existing public site HTML – unchanged)

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>NeoMonster – Admin Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootswatch@5.3.2/dist/cyborg/bootstrap.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="30">
    <style>
        :root { --primary: #3B82F6; }
        body { background: #0a0a1a; }
        .dashboard-container { max-width: 1300px; margin: auto; padding: 30px 20px; }
        .card { border: none; border-radius: 1rem; background: #111133; border: 1px solid rgba(59,130,246,0.1); }
        .card-header { background: #1e1e4a; border-radius: 1rem 1rem 0 0 !important; font-weight: bold; color: var(--primary); }
        .badge-success { background: #00b894; }
        .badge-danger { background: #d63031; }
        .table-dark { --bs-table-bg: #0f3460; border-radius: 0.5rem; overflow: hidden; }
        .btn-warning { background: #f59e0b; border: none; }
        .btn-primary { background: var(--primary); border: none; }
        .btn-back { background: var(--primary); border: none; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4" style="background: #0a0a1a !important; border-bottom: 1px solid rgba(59,130,246,0.15);">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/" style="color: var(--primary) !important;">
                <img src="{{ bot_avatar }}" width="35" height="35" class="rounded-circle me-2"> NeoMonster
            </a>
            <div>
                <a href="/" class="btn btn-back btn-sm">← Public Site</a>
                {% if logged_in %}
                <a href="/logout" class="btn btn-secondary btn-sm ms-2">Logout</a>
                {% else %}
                <a href="/login" class="btn btn-primary btn-sm ms-2">Login with Discord</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="dashboard-container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="fw-bold" style="color: var(--primary);">🛡️ Admin Dashboard</h1>
                <p class="text-muted mb-0">Real‑time security monitoring for your server</p>
            </div>
            <div class="text-end">
                <p class="mb-0 small">Status: <span class="badge bg-success">Online</span></p>
                <p class="mb-0 small">Guilds: {{ guild_count }}</p>
            </div>
        </div>

        {% if not logged_in %}
        <div class="alert alert-info">Please <a href="/login">login with Discord</a> to see your servers.</div>
        {% else %}
        <div class="card mb-4">
            <div class="card-header">Select Server</div>
            <div class="card-body">
                <form method="get" action="/dashboard" class="row g-3 align-items-center">
                    <div class="col-auto flex-grow-1">
                        <select name="guild_id" class="form-select" onchange="this.form.submit()">
                            <option value="">-- Choose a server --</option>
                            {% for g in all_guilds %}
                            <option value="{{ g.id }}" {% if g.id == guild_id %}selected{% endif %}>{{ g.name }} ({{ g.member_count }} members)</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-auto"><button type="submit" class="btn btn-primary">Load</button></div>
                </form>
            </div>
        </div>

        {% if guild_id and guild_id in user_guild_ids %}
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card text-white">
                    <div class="card-body">
                        <h5 class="card-title">Anti‑Nuke Status</h5>
                        <p class="card-text display-6">
                            {% if antinuke_enabled %}
                            <span class="badge bg-success">ENABLED</span>
                            {% else %}
                            <span class="badge bg-danger">DISABLED</span>
                            {% endif %}
                        </p>
                        <a href="/toggle?guild_id={{ guild_id }}" class="btn btn-warning btn-sm">
                            {{ 'Disable' if antinuke_enabled else 'Enable' }}
                        </a>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white">
                    <div class="card-body">
                        <h5 class="card-title">Total Events</h5>
                        <p class="card-text display-6">{{ logs|length }}</p>
                        <p class="text-muted small">Last 20 events shown</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white">
                    <div class="card-body">
                        <h5 class="card-title">Quick Actions</h5>
                        <a href="/logs?guild_id={{ guild_id }}" class="btn btn-primary btn-sm mb-2">View Raw JSON</a>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">Recent Security Events</div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-dark table-hover">
                        <thead><tr><th>Time</th><th>User ID</th><th>Event</th><th>Punishment</th></tr></thead>
                        <tbody>
                            {% for log in logs %}
                            <tr><td>{{ log[0] }}</td><td><code>{{ log[1] }}</code></td><td><span class="badge bg-warning">{{ log[2] }}</span></td><td><span class="badge bg-danger">{{ log[3] }}</span></td></tr>
                            {% endfor %}
                            {% if not logs %}<tr><td colspan="4" class="text-center text-muted">No security events yet.</td></tr>{% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {% else %}
        <div class="alert alert-warning">You don't have access to that server, or it's not protected by NeoMonster.</div>
        {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

# ---------- Routes ----------
@app.route("/")
def landing():
    bot = app.config.get("bot")
    if not bot: return "Bot still starting up.", 503
    guild_count = len(bot.guilds)
    bot_avatar = bot.user.display_avatar.url
    return render_template_string(LANDING_HTML, bot_avatar=bot_avatar, guild_count=guild_count)

@app.route("/login")
def login():
    return redirect(get_oauth_url())

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code: return "Authorization failed.", 400
    try:
        token_data = exchange_code(code)
        access_token = token_data['access_token']
        user_guilds = get_user_guilds(access_token)
        session['guild_ids'] = [g['id'] for g in user_guilds]
        session['guild_names'] = {g['id']: g['name'] for g in user_guilds}
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Login error: {e}", 500

@app.route("/dashboard")
def dashboard():
    if 'guild_ids' not in session:
        return redirect(url_for('login'))

    bot = app.config.get("bot")
    if not bot: return "Bot not initialized.", 500

    user_guild_ids = session['guild_ids']
    bot_guilds = {g.id: g for g in bot.guilds if g.id in user_guild_ids}
    all_guilds = [{"id": g.id, "name": g.name, "member_count": g.member_count} for g in bot_guilds.values()]
    
    guild_id = request.args.get("guild_id", type=int)
    if not guild_id and all_guilds:
        guild_id = all_guilds[0]["id"]
    
    if guild_id and guild_id not in bot_guilds:
        guild_id = None

    guild_count = len(bot_guilds)
    antinuke_enabled = get_antinuke_status(guild_id) if guild_id else None
    logs = get_recent_logs(guild_id) if guild_id else []
    logs = [(format_time(row[0]), row[1], row[2], row[3]) for row in logs]
    bot_avatar = bot.user.display_avatar.url

    return render_template_string(DASHBOARD_HTML,
                                  guild_id=guild_id,
                                  all_guilds=all_guilds,
                                  guild_count=guild_count,
                                  antinuke_enabled=antinuke_enabled,
                                  logs=logs,
                                  bot_avatar=bot_avatar,
                                  logged_in=True,
                                  user_guild_ids=user_guild_ids)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route("/toggle")
def toggle():
    guild_id = request.args.get("guild_id", type=int)
    if not guild_id: return "Missing guild_id", 400
    if 'guild_ids' not in session or guild_id not in session['guild_ids']:
        return redirect(url_for('login'))

    current = get_antinuke_status(guild_id)
    new_val = 0 if current else 1
    conn = get_db()
    conn.execute("UPDATE guild_settings SET antinuke_enabled = ? WHERE guild_id = ?", (new_val, guild_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard', guild_id=guild_id))

@app.route("/logs")
def view_logs():
    guild_id = request.args.get("guild_id", type=int)
    if not guild_id or ('guild_ids' in session and guild_id not in session['guild_ids']):
        return jsonify({"error": "Unauthorized"}), 403
    logs = get_recent_logs(guild_id, 50)
    return jsonify([dict(zip(["timestamp", "user_id", "event_type", "punishment"], row)) for row in logs])

# ---------- Public API (unchanged) ----------
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