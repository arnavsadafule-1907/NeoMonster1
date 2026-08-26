import os
from libsql_client import create_client
from dotenv import load_dotenv

load_dotenv()

# Read Turso credentials
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# If Turso is configured, use it; otherwise fall back to SQLite (local dev)
if TURSO_URL and TURSO_TOKEN:
    # Create a single async client that persists across calls
    _client = None

    async def get_client():
        global _client
        if _client is None:
            # Create the client (async)
            _client = await create_client(TURSO_URL, auth_token=TURSO_TOKEN)
        return _client

    async def execute_query(sql, params=()):
        client = await get_client()
        return await client.execute(sql, params)

    async def get_db():
        # Return the client itself – all methods are awaitable
        return await get_client()

    async def init_db():
        client = await get_client()
        await _init_tables(client)

    async def add_log(guild_id, user_id, event_type, punishment):
        from datetime import datetime, timezone
        await execute_query(
            "INSERT INTO antinuke_logs (guild_id, user_id, event_type, punishment, timestamp) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, event_type, punishment, datetime.now(timezone.utc).isoformat())
        )

else:
    # Fallback to aiosqlite for local development
    import aiosqlite
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    async def get_db():
        db = await aiosqlite.connect(DATABASE_PATH)
        db.row_factory = aiosqlite.Row
        return db

    async def init_db():
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await _init_tables(db)

    async def add_log(guild_id, user_id, event_type, punishment):
        from datetime import datetime, timezone
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO antinuke_logs (guild_id, user_id, event_type, punishment, timestamp) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, event_type, punishment, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()


async def _init_tables(conn):
    # SQLite syntax (works with both aiosqlite and libsql)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            modules TEXT DEFAULT '{"channel_create": true, "channel_delete": true, "role_create": true, "role_delete": true, "ban": true, "kick": true, "webhook_create": true, "webhook_delete": true}',
            thresholds TEXT DEFAULT '{"channel_create": 3, "channel_delete": 3, "role_create": 3, "role_delete": 3, "ban": 2, "kick": 2, "webhook_create": 2, "webhook_delete": 2}',
            time_window INTEGER DEFAULT 10,
            punishment TEXT DEFAULT 'strip',
            quarantine_role_id INTEGER DEFAULT 0,
            log_channel_id INTEGER DEFAULT 0,
            antinuke_enabled INTEGER DEFAULT 1
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS whitelist (
            guild_id INTEGER NOT NULL,
            user_id INTEGER DEFAULT 0,
            role_id INTEGER DEFAULT 0,
            UNIQUE(guild_id, user_id, role_id)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS antinuke_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            punishment TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    await conn.commit()