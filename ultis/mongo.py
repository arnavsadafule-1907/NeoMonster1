import os
import logging
from typing import Optional

# pyright: reportMissingImports=false
logger = logging.getLogger("discord.mongo")

try:
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore[import-not-found]
    MOTOR_AVAILABLE = True
except ImportError:
    AsyncIOMotorClient = None
    MOTOR_AVAILABLE = False
    logger.warning("motor not installed — MongoDB features disabled")

_client: Optional[object] = None
_db = None


async def connect_mongo():
    """Connect to MongoDB. Returns the database or None."""
    global _client, _db

    if not MOTOR_AVAILABLE:
        logger.warning("MongoDB skipped: motor library not installed")
        return None

    uri = os.getenv("MONGO_URI")
    if not uri or not uri.strip():
        logger.info("MongoDB disabled: MONGO_URI not set")
        return None

    try:
        _client = AsyncIOMotorClient(
            uri.strip(),
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
            socketTimeoutMS=20000,
        )
        db_name = os.getenv("MONGO_DB_NAME", "neomonster")
        _db = _client[db_name]

        # Verify connection
        await _client.admin.command("ping")
        logger.info(f"MongoDB connected: db={db_name}")
        return _db

    except Exception as e:
        logger.error(f"MongoDB connection failed: {type(e).__name__}: {e}")
        _client = None
        _db = None
        return None


def get_db():
    """Get the active MongoDB database handle (or None if not connected)."""
    return _db


def is_connected() -> bool:
    return _db is not None


async def close_mongo():
    global _client, _db
    if _client:
        try:
            _client.close()
        except Exception:
            pass
        _client = None
        _db = None