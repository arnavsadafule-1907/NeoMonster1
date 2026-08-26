import os
from libsql_client import create_client_sync, create_client_async
from dotenv import load_dotenv

load_dotenv()

# Turso environment variables
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# Fallback to SQLite for local development
if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
    import aiosqlite
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/security.db")
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    # Async get_db for local dev (using aiosqlite)
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
else:
    # Turso client (production)
    def get_client_sync():
        return create_client_sync(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    
    async def get_db():
        return create_client_async(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    
    async def init_db():
        client = get_client_sync()
        await _init_tables(client)
        client.close()
    
    async def add_log(guild_id, user_id, event_type, punishment):
        from datetime import datetime, timezone
        client = get_client_sync()
        await client.execute(
            "INSERT INTO antinuke_logs (guild_id, user_id, event_type, punishment, timestamp) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, event_type, punishment, datetime.now(timezone.utc).isoformat())
        )
        client.close()

# Shared table creation logic
async def _init_tables(conn):
    # Turso uses SQLite syntax – same as aiosqlite
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            modules TEXT DEFAULT '{
                "channel_create": true,
                "channel_delete": true,
                "role_create": true,
                "role_delete": true,
                "ban": true,
                "kick": true,
                "webhook_create": true,
                "webhook_delete": true
            }',
            thresholds TEXT DEFAULT '{
                "channel_create": 3,
                "channel_delete": 3,
                "role_create": 3,
                "role_delete": 3,
                "ban": 2,
                "kick": 2,
                "webhook_create": 2,
                "webhook_delete": 2
            }',
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
    # Add other tables as needed (ticket_types, leaves, staff_stats, etc.)
    # You can copy the CREATE TABLE statements from your old db.py
    await conn.commit()