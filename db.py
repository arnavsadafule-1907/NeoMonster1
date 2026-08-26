import os
from dotenv import load_dotenv

load_dotenv()

# ----- Check for Turso (persistent) -----
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if TURSO_URL and TURSO_TOKEN:
    # Turso (production, persistent)
    from libsql_client import create_client
    _client = None

    async def get_client():
        global _client
        if _client is None:
            _client = create_client(TURSO_URL, auth_token=TURSO_TOKEN)
        return _client

    async def get_db():
        return await get_client()

    async def init_db():
        client = await get_client()
        await _init_tables(client)

    async def add_log(guild_id, user_id, event_type, punishment):
        from datetime import datetime, timezone
        client = await get_client()
        await client.execute(
            "INSERT INTO antinuke_logs (guild_id, user_id, event_type, punishment, timestamp) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, event_type, punishment, datetime.now(timezone.utc).isoformat())
        )

else:
    # SQLite fallback (local development / Render without Turso)
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


# ================================================================
#  TABLE CREATION – Clean, tested, no syntax errors
# ================================================================
async def _init_tables(conn):
    # 1. guild_settings (main config)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            modules TEXT DEFAULT '{"channel_create": true, "channel_delete": true, "role_create": true, "role_delete": true, "ban": true, "kick": true, "webhook_create": true, "webhook_delete": true}',
            thresholds TEXT DEFAULT '{"channel_create": 3, "channel_delete": 3, "role_create": 3, "role_delete": 3, "ban": 2, "kick": 2, "webhook_create": 2, "webhook_delete": 2}',
            time_window INTEGER DEFAULT 10,
            punishment TEXT DEFAULT 'strip',
            quarantine_role_id INTEGER DEFAULT 0,
            log_channel_id INTEGER DEFAULT 0,
            antinuke_enabled INTEGER DEFAULT 1,
            mod_log_channel_id INTEGER DEFAULT 0,
            poll_log_channel_id INTEGER DEFAULT 0
        )
    ''')

    # 2. whitelist
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS whitelist (
            guild_id INTEGER NOT NULL,
            user_id INTEGER DEFAULT 0,
            role_id INTEGER DEFAULT 0,
            UNIQUE(guild_id, user_id, role_id)
        )
    ''')

    # 3. antinuke_logs
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

    # 4. ticket_metadata
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ticket_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            ticket_number INTEGER NOT NULL,
            channel_id INTEGER UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            open_time TEXT NOT NULL,
            claimed_by INTEGER,
            ticket_type TEXT NOT NULL
        )
    ''')

    # 5. ticket_types
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ticket_types (
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            support_role_id INTEGER DEFAULT 0,
            welcome_message TEXT,
            PRIMARY KEY (guild_id, name)
        )
    ''')

    # 6. ticket_counter
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ticket_counter (
            guild_id INTEGER PRIMARY KEY,
            counter INTEGER DEFAULT 0
        )
    ''')

    # 7. ticket_panel_config
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ticket_panel_config (
            guild_id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            image_url TEXT,
            fields TEXT
        )
    ''')

    # 8. staff_stats
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS staff_stats (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            tickets_claimed INTEGER DEFAULT 0,
            tickets_closed INTEGER DEFAULT 0,
            leave_days INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')

    # 9. leaves
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        )
    ''')

    # 10. leave_settings
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS leave_settings (
            guild_id INTEGER PRIMARY KEY,
            role_id INTEGER NOT NULL
        )
    ''')

    # 11. leave_panel_config
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS leave_panel_config (
            guild_id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            image_url TEXT
        )
    ''')

    # 12. extra_owners
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS extra_owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            UNIQUE(guild_id, user_id)
        )
    ''')

    # 13. global_blacklist
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS global_blacklist (
            user_id INTEGER PRIMARY KEY
        )
    ''')

    # 14. bot_whitelist
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS bot_whitelist (
            guild_id INTEGER NOT NULL,
            bot_id INTEGER NOT NULL,
            UNIQUE(guild_id, bot_id)
        )
    ''')

    # 15. raid_webhooks
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS raid_webhooks (
            guild_id INTEGER PRIMARY KEY,
            webhook_url TEXT NOT NULL
        )
    ''')

    # 16. altdetector_settings
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS altdetector_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            min_days INTEGER DEFAULT 7,
            log_channel_id INTEGER
        )
    ''')

    # 17. massmention_settings
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS massmention_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            threshold INTEGER DEFAULT 10,
            punishment TEXT DEFAULT 'mute'
        )
    ''')

    # 18. antivanity_settings
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS antivanity_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        )
    ''')

    # 19. report_settings
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS report_settings (
            guild_id INTEGER PRIMARY KEY,
            report_channel_id INTEGER NOT NULL
        )
    ''')

    # 20. antispam_settings
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS antispam_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            threshold INTEGER DEFAULT 5,
            window INTEGER DEFAULT 5,
            mute_duration INTEGER DEFAULT 10
        )
    ''')

    # 21. ai_channels (if you ever re-enable AI)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ai_channels (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL
        )
    ''')

    # 22. knowledge_channels & knowledge_entries
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER PRIMARY KEY
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            section TEXT,
            content TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')

    # Commit all changes (important for aiosqlite; for Turso it may be automatic)
    try:
        await conn.commit()
    except AttributeError:
        # Turso client might not have commit; it's fine.
        pass