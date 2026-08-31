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

# ---------- FIXED: Safely parse OWNER_IDS ----------
try:
    owner_ids_str = os.getenv("OWNER_IDS", "")
    if owner_ids_str:
        OWNER_IDS = set(int(x.strip()) for x in owner_ids_str.split(",") if x.strip())
    else:
        OWNER_IDS = set()
except ValueError:
    OWNER_IDS = set()

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
    return f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri=https%3A%2F%2FNeoMonster1-production.up.railway.app%2Fcallback&response_type=code&scope=identify+guilds"

def exchange_code(code):
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'https://neomonster1.onrender.comcallback'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
    r.raise_for_status()
    return r.json()

def get_user_info(token):
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get('https://discord.com/api/users/@me', headers=headers)
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

# ---------- LANDING PAGE (unchanged) ----------
LANDING_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>NeoMonster – Ultimate Discord Security Bot</title>
    <meta name="description" content="Protect your Discord server from nukes, raids, and spam with NeoMonster – the most advanced security bot.">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg: #0a0a1a;
            --card-bg: #111133;
            --primary: #3B82F6;
            --primary-glow: rgba(59,130,246,0.4);
            --secondary: #60A5FA;
            --accent: #93C5FD;
            --text: #eee;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; line-height: 1.6; }
        .navbar { background: rgba(10,10,26,0.95); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(59,130,246,0.15); position: fixed; top: 0; width: 100%; z-index: 1000; }
        .nav-container { max-width: 1200px; margin: 0 auto; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
        .nav-brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: white; font-weight: 700; font-size: 1.3rem; }
        .nav-brand img { width: 40px; height: 40px; border-radius: 50%; border: 2px solid var(--primary); }
        .hero { text-align: center; padding: 160px 20px 80px; background: radial-gradient(circle at 30% 40%, #0d1b3e 0%, #0a0a1a 70%); }
        .hero img { width: 140px; border-radius: 50%; border: 4px solid var(--primary); box-shadow: 0 0 40px var(--primary-glow); animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-15px); } }
        .hero h1 { font-size: 4rem; font-weight: 800; margin: 20px 0 15px; background: linear-gradient(135deg, var(--primary), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .hero p { font-size: 1.2rem; color: #b0b0d0; max-width: 650px; margin: 0 auto 35px; }
        .btn-invite { background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white !important; font-weight: 600; padding: 16px 40px; border-radius: 50px; font-size: 1.2rem; transition: all 0.3s ease; text-decoration: none; display: inline-block; border: none; cursor: pointer; }
        .btn-invite:hover { transform: translateY(-3px); box-shadow: 0 20px 40px var(--primary-glow); color: white !important; }
        .btn-secondary { background: transparent; color: var(--primary) !important; border: 2px solid var(--primary); padding: 14px 35px; border-radius: 50px; font-weight: 600; text-decoration: none; transition: all 0.3s ease; margin-left: 15px; }
        .btn-secondary:hover { background: rgba(59,130,246,0.1); color: var(--primary) !important; }
        .stats { display: flex; justify-content: center; gap: 30px; flex-wrap: wrap; margin-top: 50px; }
        .stat-item { background: var(--card-bg); padding: 25px 40px; border-radius: 16px; text-align: center; border: 1px solid rgba(59,130,246,0.15); }
        .stat-number { font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, var(--primary), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .stat-label { color: #888; font-size: 0.9rem; margin-top: 5px; }
        .section { padding: 80px 20px; max-width: 1200px; margin: auto; }
        .section h2 { text-align: center; font-weight: 800; font-size: 2.5rem; margin-bottom: 20px; color: var(--primary); }
        .section-subtitle { text-align: center; color: #888; margin-bottom: 50px; font-size: 1.1rem; }
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px; }
        .feature-card { background: var(--card-bg); border-radius: 20px; padding: 35px; transition: all 0.3s; border: 1px solid rgba(59,130,246,0.1); position: relative; overflow: hidden; }
        .feature-card::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 3px; background: linear-gradient(90deg, var(--primary), var(--accent)); transform: scaleX(0); transition: transform 0.3s ease; }
        .feature-card:hover::before { transform: scaleX(1); }
        .feature-card:hover { transform: translateY(-8px); box-shadow: 0 20px 40px rgba(59,130,246,0.15); }
        .feature-icon { font-size: 2.5rem; margin-bottom: 20px; display: inline-block; }
        .feature-card h5 { font-size: 1.3rem; font-weight: 700; margin-bottom: 10px; color: var(--primary); }
        .feature-card p { color: #999; font-size: 0.95rem; }
        .footer { text-align: center; padding: 50px 20px; border-top: 1px solid rgba(59,130,246,0.15); margin-top: 60px; color: #666; }
        .footer a { color: var(--primary); text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
        @media (max-width: 768px) {
            .hero h1 { font-size: 2.5rem; }
            .hero p { font-size: 1rem; }
            .stats { gap: 15px; }
            .stat-item { padding: 20px 25px; }
            .btn-secondary { margin-left: 0; margin-top: 15px; display: block; }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <a href="/" class="nav-brand">
                <img src="{{ bot_avatar }}" alt="NeoMonster Logo">
                NeoMonster
            </a>
        </div>
    </nav>

    <section class="hero">
        <img src="{{ bot_avatar }}" alt="NeoMonster Bot">
        <h1>NeoMonster</h1>
        <p>The most advanced Discord security bot. Real‑time anti‑nuke protection, intelligent moderation, and a powerful dashboard – trusted by {{ guild_count }}+ servers.</p>
        <div>
            <a href="https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473370870&integration_type=0&scope=bot+applications.commands" class="btn-invite" target="_blank">
                <i class="fas fa-shield-alt me-2"></i> Invite to Server
            </a>
            <a href="#features" class="btn-secondary">
                <i class="fas fa-star me-2"></i> View Features
            </a>
        </div>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number">{{ guild_count }}</div>
                <div class="stat-label">Servers Protected</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">65+</div>
                <div class="stat-label">Commands</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">24/7</div>
                <div class="stat-label">Uptime</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">&lt;50ms</div>
                <div class="stat-label">Response Time</div>
            </div>
        </div>
    </section>

    <section class="section" id="features">
        <h2>Why NeoMonster?</h2>
        <p class="section-subtitle">Enterprise‑grade protection for your Discord community</p>
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon">🛡️</div>
                <h5>Anti‑Nuke Protection</h5>
                <p>Real‑time detection of channel/role deletions, mass bans, and webhook spam. Automatic punishment within seconds.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🤖</div>
                <h5>Auto‑Moderation</h5>
                <p>Spam detection, invite blocking, bad word filter, mass mention protection – all configurable per server.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🎉</div>
                <h5>Giveaways</h5>
                <p>Button‑based giveaways with automatic winner selection, rerolls, and role requirements.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <h5>Web Dashboard</h5>
                <p>Monitor your server in real time, toggle anti‑nuke, view security logs – from any browser.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📝</div>
                <h5>Message Logging</h5>
                <p>Track deleted and edited messages with full details. Never lose evidence of abuse.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🕵️</div>
                <h5>Alt Detection</h5>
                <p>Flag suspiciously new accounts on join. Prevent ban evasion and raid alts automatically.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">💾</div>
                <h5>Backup & Restore</h5>
                <p>Create full server backups in one click. Restore instantly after an attack.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔔</div>
                <h5>Raid Alerts</h5>
                <p>Get instant notifications via Discord webhooks when your server is under attack – even on mobile.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">👑</div>
                <h5>Role Management</h5>
                <p>Custom roles, admin/nuke hierarchy, whitelist system – full control over permissions.</p>
            </div>
        </div>
    </section>

    <footer class="footer">
        <p>© 2026 <a href="/">NeoMonster</a>. All rights reserved.</p>
        <p style="margin-top: 5px;">
            <a href="https://discord.com/oauth2/authorize?client_id=1528368412093579376&permissions=1100473370870&integration_type=0&scope=bot+applications.commands" target="_blank">Invite</a> •
            <a href="mailto:contact@olympusbot.in">Contact</a> •
            <a href="https://discord.gg/f8zTc4tmHx" target="_blank">Support Server</a>
        </p>
    </footer>
</body>
</html>
"""

# ---------- DASHBOARD HTML (unchanged) ----------
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

# ---------- Debug route (unchanged) ----------
@app.route("/debug")
def debug():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    bot = app.config.get("bot")
    if not bot: return "Bot not initialized.", 500

    token = session.get('access_token')
    if token:
        try:
            user_guilds = get_user_guilds(token)
            oauth_guilds = [{"id": g['id'], "name": g['name'], "owner": g['owner'], "permissions": g['permissions']} for g in user_guilds]
        except:
            oauth_guilds = "Failed to fetch"
    else:
        oauth_guilds = "No token"

    bot_guilds = [{"id": g.id, "name": g.name} for g in bot.guilds]

    return jsonify({
        "your_discord_id": session['user_id'],
        "is_bot_owner": session.get('is_bot_owner', False),
        "owner_ids_in_env": list(OWNER_IDS),
        "oauth_guilds": oauth_guilds,
        "bot_guilds": bot_guilds
    })

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
        session['access_token'] = access_token

        user_info = get_user_info(access_token)
        session['user_id'] = int(user_info['id'])
        session['is_bot_owner'] = session['user_id'] in OWNER_IDS

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

    if session.get('is_bot_owner'):
        bot_guilds = {g.id: g for g in bot.guilds}
    else:
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

    viewable_guild_ids = list(bot_guilds.keys()) if session.get('is_bot_owner') else session['guild_ids']

    return render_template_string(DASHBOARD_HTML,
                                  guild_id=guild_id,
                                  all_guilds=all_guilds,
                                  guild_count=guild_count,
                                  antinuke_enabled=antinuke_enabled,
                                  logs=logs,
                                  bot_avatar=bot_avatar,
                                  logged_in=True,
                                  user_guild_ids=viewable_guild_ids)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route("/toggle")
def toggle():
    guild_id = request.args.get("guild_id", type=int)
    if not guild_id: return "Missing guild_id", 400
    if not session.get('is_bot_owner') and ('guild_ids' not in session or guild_id not in session['guild_ids']):
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
    if not guild_id: return jsonify({"error": "Missing guild_id"}), 400
    if not session.get('is_bot_owner') and ('guild_ids' not in session or guild_id not in session['guild_ids']):
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