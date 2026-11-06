import os
import re
from typing import Any, Optional

try:
    import discord
except ImportError:
    discord = None

# Comprehensive Built-In Unicode Fallback Registry
_DEFAULT_FALLBACKS: dict[str, str] = {
    # Security
    "shield": "🛡️",
    "guard": "🛡️",
    "protection": "🛡️",
    "modshield": "🛡️",
    "lite_modshield": "🛡️",
    "firewall": "🔥",
    "swords": "⚔️",
    "lock": "🔒",
    "unlock": "🔓",
    "key": "🔑",
    "secure": "🛡️",
    # Moderation
    "ban": "🔨",
    "kick": "👢",
    "mute": "🔇",
    "unmute": "🔊",
    "deafened": "🔕",
    "undeafened": "🔔",
    "timeout": "⏱️",
    "warn": "⚠️",
    "warning": "⚠️",
    "clear": "🧹",
    "moderator": "🛡️",
    "mod_badge": "🔰",
    "certified_mod": "🎖️",
    "head_moderator": "🛡️",
    "trial_moderator": "🔰",
    "moderation": "🔨",
    "wrench": "🔧",
    "gear": "⚙️",
    # Anti-Raid & Anti-Nuke
    "anti_raid": "🚨",
    "anti_nuke": "🛡️",
    "raid_alert": "🚨",
    "siren": "🚨",
    "bot_detection": "🤖",
    "iamabot": "🤖",
    "attack_warning": "🚨",
    "suspicious_activity": "👁️",
    "protection_enabled": "🛡️",
    "emergency": "⚔️",
    # Verification
    "verified": "☑️",
    "verified_blue": "☑️",
    "verified_badge": "🎖️",
    "unverified": "✖️",
    "captcha": "🔹",
    "pending": "⏳",
    "approved": "✅",
    "rejected": "❌",
    "verification": "☑️",
    # Logging
    "audit_logs": "📜",
    "message_deleted": "🗑️",
    "message_edited": "✏️",
    "member_joined": "📥",
    "member_left": "📤",
    "role_updated": "🏷️",
    "channel_updated": "📁",
    "voice_activity": "🎙️",
    "server_logs": "📑",
    "microphone": "🎙️",
    "rules": "📜",
    # Server Management
    "server": "🌐",
    "settings": "⚙️",
    "configuration": "⚙️",
    "admin": "👑",
    "owner": "👑",
    "crown": "👑",
    "staff": "👥",
    "developer": "💻",
    "roles": "🏷️",
    "channels": "📁",
    "announcement": "📢",
    "wave": "👋",
    # Tickets & Support
    "ticket": "🎫",
    "support": "💬",
    "open_ticket": "📩",
    "close_ticket": "🔒",
    "claim_ticket": "📌",
    "resolved": "✅",
    # Status & Notifications
    "success": "✅",
    "tick": "✅",
    "error": "❌",
    "cross": "❌",
    "info": "ℹ️",
    "information": "ℹ️",
    "loading": "⏳",
    "online": "🟢",
    "offline": "🔴",
    "enabled": "✅",
    "disabled": "❌",
    "double_check": "✅",
    # Navigation
    "home": "🏠",
    "search": "🔍",
    "menu": "📋",
    "back": "◀️",
    "next": "▶️",
    "refresh": "🔄",
    # Statistics
    "members": "👥",
    "users": "👥",
    "bots": "🤖",
    "graphs": "📊",
    "analytics": "📈",
    "growth": "🚀",
    "rocket": "🚀",
    "activity": "⚡",
    "statistics": "📊",
    "sparkles": "✨",
    "dice": "🎲",
    "party": "🎉",
    # AutoMod
    "spam_detection": "🛑",
    "slowmode": "⏱️",
    "links": "🔗",
    "link": "🔗",
    "bad_words": "🚫",
    "suspicious_messages": "⚠️",
    "filtered_messages": "⛔",
    "blocked_content": "🚫",
    # Configuration
    "setup": "🛠️",
    "save": "💾",
    "reset": "🔄",
    "edit": "✏️",
    "delete": "🗑️",
    "enable": "✅",
    "disable": "❌",
    "dashboard": "🎛️",
}

# Regex patterns supporting multiple syntax variations
_ENTRY_ARROW_OR_DASH_REGEX = re.compile(
    r'([a-zA-Z0-9_]+)\s*=\s*"?((?:<)(?:a)?:[a-zA-Z0-9_]+:[0-9]+>)"?\s*(?:->|-)\s*"([^"]*)"'
)
_ENTRY_LEGACY_DASH_REGEX = re.compile(
    r'^\s*([a-zA-Z0-9_]+)\s*-\s*"([^"]*)"\s*-\s*"([^"]*)"\s*$'
)
_ENTRY_SIMPLE_EQ_REGEX = re.compile(
    r'([a-zA-Z0-9_]+)\s*=\s*"?((?:<)(?:a)?:[a-zA-Z0-9_]+:[0-9]+>)"?'
)
_CUSTOM_EMOJI_REGEX = re.compile(r'^<(a)?:([a-zA-Z0-9_]+):([0-9]+)>$')

_APPLICATION_EMOJI_IDS: set[int] = set()
_EMOJI_REGISTRY: dict[str, tuple[str, str, int | None]] = {}
_CATEGORIES: dict[str, list[str]] = {}
_CACHE: dict[str, str] = {}
_BOT_INSTANCE: Any = None


def _extract_emoji_id(custom_str: str) -> tuple[int | None, bool]:
    m = _CUSTOM_EMOJI_REGEX.match(custom_str)
    if not m:
        return None, False
    is_anim = bool(m.group(1))
    try:
        eid = int(m.group(3))
        return eid, is_anim
    except ValueError:
        return None, is_anim


def _parse_file(file_path: str) -> dict[str, tuple[str, str, int | None]]:
    registry: dict[str, tuple[str, str, int | None]] = {}
    global _CATEGORIES
    _CATEGORIES = {}
    current_category = "GENERAL"

    if not os.path.exists(file_path):
        return registry

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                if stripped.startswith("[") and stripped.endswith("]"):
                    current_category = stripped[1:-1].strip()
                    if current_category not in _CATEGORIES:
                        _CATEGORIES[current_category] = []
                    continue
                elif stripped.isupper() and "=" not in stripped and "-" not in stripped and ">" not in stripped:
                    current_category = stripped.strip()
                    if current_category not in _CATEGORIES:
                        _CATEGORIES[current_category] = []
                    continue

                m_leg = _ENTRY_LEGACY_DASH_REGEX.match(stripped)
                if m_leg:
                    name, custom, fallback = m_leg.groups()
                    name = name.lower()
                    if name not in registry:
                        eid, _ = _extract_emoji_id(custom)
                        registry[name] = (custom, fallback, eid)
                        if current_category not in _CATEGORIES:
                            _CATEGORIES[current_category] = []
                        _CATEGORIES[current_category].append(name)
                    continue

                m_arrow = _ENTRY_ARROW_OR_DASH_REGEX.findall(stripped)
                if m_arrow:
                    for name, custom, fallback in m_arrow:
                        name = name.lower()
                        if name not in registry:
                            eid, _ = _extract_emoji_id(custom)
                            registry[name] = (custom, fallback, eid)
                            if current_category not in _CATEGORIES:
                                _CATEGORIES[current_category] = []
                            _CATEGORIES[current_category].append(name)
                    continue

                m_eq = _ENTRY_SIMPLE_EQ_REGEX.findall(stripped)
                if m_eq:
                    for name, custom in m_eq:
                        name = name.lower()
                        if name not in registry:
                            eid, _ = _extract_emoji_id(custom)
                            fallback = _DEFAULT_FALLBACKS.get(name, "🔹")
                            registry[name] = (custom, fallback, eid)
                            if current_category not in _CATEGORIES:
                                _CATEGORIES[current_category] = []
                            _CATEGORIES[current_category].append(name)
                    continue
    except OSError:
        pass

    return registry


def _load_application_ids(base_dir: str) -> None:
    global _APPLICATION_EMOJI_IDS
    for fn in ("discord_8page_emojis.json", "discord_uploaded_emojis.json"):
        json_path = os.path.join(base_dir, fn)
        if os.path.exists(json_path):
            import json
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        if "id" in item:
                            try:
                                _APPLICATION_EMOJI_IDS.add(int(item["id"]))
                            except (ValueError, TypeError):
                                continue
                break
            except (OSError, json.JSONDecodeError):
                continue


_SENTINEL = object()


def init_emojis(bot: Any = _SENTINEL, file_path: str = "emojis.txt") -> None:
    global _EMOJI_REGISTRY, _BOT_INSTANCE, _CACHE
    if bot is not _SENTINEL:
        _BOT_INSTANCE = bot
    if not os.path.isabs(file_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _load_application_ids(base_dir)
        file_path = os.path.join(base_dir, file_path)
    else:
        base_dir = os.path.dirname(file_path)
        _load_application_ids(base_dir)

    _EMOJI_REGISTRY = _parse_file(file_path)
    _CACHE.clear()


def reload_emojis(file_path: str = "emojis.txt") -> None:
    init_emojis(_BOT_INSTANCE, file_path)


def get_emoji(name: str, fallback_to_unicode: bool = False) -> str:
    key = name.lower()
    cache_key = f"{key}_fb" if fallback_to_unicode else key
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if not _EMOJI_REGISTRY:
        init_emojis(_BOT_INSTANCE)

    entry = _EMOJI_REGISTRY.get(key)
    if not entry:
        fb = _DEFAULT_FALLBACKS.get(key, "")
        _CACHE[cache_key] = fb
        return fb

    custom, fallback, emoji_id = entry

    if not fallback:
        fallback = _DEFAULT_FALLBACKS.get(key, "🔹")

    if fallback_to_unicode:
        _CACHE[cache_key] = fallback
        return fallback

    if not emoji_id or emoji_id == 123456789012345678:
        resolved = fallback
    elif _APPLICATION_EMOJI_IDS and emoji_id in _APPLICATION_EMOJI_IDS:
        resolved = custom
    elif _BOT_INSTANCE is not None and hasattr(_BOT_INSTANCE, "get_emoji"):
        discord_emoji = _BOT_INSTANCE.get_emoji(emoji_id)
        resolved = str(discord_emoji) if discord_emoji else fallback
    else:
        resolved = custom if custom else fallback

    _CACHE[cache_key] = resolved
    return resolved


def get_partial_emoji(name: str) -> Optional[Any]:
    if discord is None:
        return None
    key = name.lower()
    entry = _EMOJI_REGISTRY.get(key)
    if not entry:
        return None
    custom, _, emoji_id = entry
    if not custom or not emoji_id:
        return None
    try:
        return discord.PartialEmoji.from_str(custom)
    except Exception:
        return None


def get_fallback(name: str) -> str:
    return get_emoji(name, fallback_to_unicode=True)


def get_raw_id(name: str) -> Optional[int]:
    entry = _EMOJI_REGISTRY.get(name.lower())
    return entry[2] if entry else None


def is_animated(name: str) -> bool:
    entry = _EMOJI_REGISTRY.get(name.lower())
    if not entry or not entry[0]:
        return False
    return entry[0].startswith("<a:")


def get_categories() -> dict[str, list[str]]:
    return dict(_CATEGORIES)


def get_registry() -> dict[str, tuple[str, str, int | None]]:
    return dict(_EMOJI_REGISTRY)