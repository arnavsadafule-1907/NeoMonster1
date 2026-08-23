import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

SECRET = os.getenv("MC_WEBHOOK_SECRET")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_MC_WEBHOOK_URL")

@app.route("/mcchat", methods=["POST"])
def mc_chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON"}), 400

    if data.get("secret") != SECRET:
        return jsonify({"error": "Invalid secret"}), 403

    player = data.get("player")
    message = data.get("message")
    server = data.get("server", "Minecraft")

    if not player or not message:
        return jsonify({"error": "Missing player/message"}), 400

    if not DISCORD_WEBHOOK_URL:
        return jsonify({"error": "Webhook not set"}), 500

    content = f"**{player}** › {message}"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": content, "username": f"{server} Chat"})

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def health():
    return "Minecraft chat bridge is running."

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5002))
    app.run(host="0.0.0.0", port=port)