import os
import sys
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

SECRET = os.getenv("MC_WEBHOOK_SECRET")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_MC_WEBHOOK_URL")

if not SECRET or not DISCORD_WEBHOOK_URL:
    print("❌ Missing environment variables. Exiting.")
    sys.exit(1)

@app.route("/mcchat", methods=["POST"])
def mc_chat():
    data = request.get_json()
    if not data or data.get("secret") != SECRET:
        return jsonify({"error": "Invalid"}), 403

    player = data.get("player")
    message = data.get("message")
    server = data.get("server", "DesireSMP")

    if not player or not message:
        return jsonify({"error": "Missing fields"}), 400

    # Build a professional embed
    embed = {
        "embeds": [{
            "title": f"💬 {server} Chat",
            "description": message,
            "color": 0x3B82F6,  # Blue
            "author": {
                "name": player,
                "icon_url": "https://minotar.net/helm/" + player + "/32.png"  # Minecraft avatar
            },
            "footer": {
                "text": "DesireSMP • Live Chat",
                "icon_url": "https://cdn.discordapp.com/avatars/1528368412093579376/bot_avatar.png"  # Your bot's avatar
            },
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=embed)
        print(f"✅ Forwarded: {player} › {message}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return "Minecraft chat bridge is running."

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5002))
    app.run(host="0.0.0.0", port=port)