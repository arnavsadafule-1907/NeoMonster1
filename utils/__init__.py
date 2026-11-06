from importlib import import_module

_EMOJI_EXPORTS = {"get_emoji", "init_emojis", "reload_emojis"}


def __getattr__(name):
	if name in _EMOJI_EXPORTS:
		value = getattr(import_module(".emoji_manager", __name__), name)
		globals()[name] = value
		return value
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["get_emoji", "init_emojis", "reload_emojis", "connect_mongo", "get_db", "is_connected", "close_mongo"]