import os
import aiosqlite
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

def get_db_path() -> str:
    """Resolve database path supporting standard DATABASE_URL or DATABASE_PATH."""
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("sqlite:///"):
            path = url[len("sqlite:///"):]
        elif url.startswith("sqlite://"):
            path = url[len("sqlite://"):]
        else:
            path = url
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        return path

    path = os.getenv("DATABASE_PATH", "./data/security.db")
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    return path

DATABASE_PATH = get_db_path()

async def get_db(db_path=None):
    """Obtain a managed aiosqlite connection with busy timeout and foreign keys enabled."""
    path = db_path or get_db_path()
    db = await aiosqlite.connect(path, timeout=10.0)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA busy_timeout = 10000;")
    await db.execute("PRAGMA foreign_keys = ON;")
    return db

@asynccontextmanager
async def transaction(db_path=None):
    """Context manager for atomic database transactions with auto-commit and rollback."""
    db = await get_db(db_path)
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()

async def init_db(db_path=None):
    """Initialize database schema, apply WAL mode, busy timeout, and create all tables/indexes."""
    path = db_path or get_db_path()
    async with aiosqlite.connect(path, timeout=10.0) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA busy_timeout = 10000;")
        await db.execute("PRAGMA synchronous = NORMAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await _init_tables(db)
        await db.commit()

async def add_log(guild_id, user_id, event_type, punishment):
    from datetime import datetime, timezone
    async with aiosqlite.connect(get_db_path(), timeout=10.0) as db:
        await db.execute(
            "INSERT INTO antinuke_logs (guild_id, user_id, event_type, punishment, timestamp) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, event_type, punishment, datetime.now(timezone.utc).isoformat())
        )
        await db.commit()

async def _init_tables(conn):
    # Core Guild & AntiNuke Settings
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

    # Tickets System
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
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ticket_counter (
            guild_id INTEGER PRIMARY KEY,
            counter INTEGER DEFAULT 0
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ticket_panel_config (
            guild_id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            image_url TEXT,
            fields TEXT,
            panel_style TEXT DEFAULT 'dropdown'
        )
    ''')

    # Staff & Leave System
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
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS leave_settings (
            guild_id INTEGER PRIMARY KEY,
            role_id INTEGER NOT NULL
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS leave_panel_config (
            guild_id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            image_url TEXT
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS staff_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_id INTEGER,
            reason TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    # Security & Protection Configs
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS extra_owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            UNIQUE(guild_id, user_id)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS global_blacklist (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_blacklist (
            guild_id INTEGER PRIMARY KEY
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS bot_whitelist (
            guild_id INTEGER NOT NULL,
            bot_id INTEGER NOT NULL,
            UNIQUE(guild_id, bot_id)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS raid_webhooks (
            guild_id INTEGER PRIMARY KEY,
            webhook_url TEXT NOT NULL
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS altdetector_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            min_days INTEGER DEFAULT 7,
            log_channel_id INTEGER
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS massmention_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            threshold INTEGER DEFAULT 10,
            punishment TEXT DEFAULT 'mute'
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS antivanity_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS report_settings (
            guild_id INTEGER PRIMARY KEY,
            report_channel_id INTEGER NOT NULL
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS antispam_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            threshold INTEGER DEFAULT 5,
            window INTEGER DEFAULT 5,
            mute_duration INTEGER DEFAULT 10
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS server_whitelists (
            guild_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            target_type TEXT NOT NULL,
            category TEXT NOT NULL,
            PRIMARY KEY (guild_id, target_id, category)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS sw_users (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, category)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS sw_roles (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            PRIMARY KEY (guild_id, role_id, category)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS sw_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            PRIMARY KEY (guild_id, channel_id, category)
        )
    ''')

    # Channels & Ignored Entities
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ai_channels (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL
        )
    ''')
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
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ignored_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            UNIQUE(guild_id, channel_id)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS ignored_entities (
            guild_id INTEGER NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, entity_type, entity_id)
        )
    ''')

    # Logging, Sticky & DM Campaigns
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS log_channels (
            guild_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            channel_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, event_type)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS sticky_messages (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            last_message_id INTEGER,
            enabled INTEGER DEFAULT 1
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS dm_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            initiator_id INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            total INTEGER DEFAULT 0,
            sent INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',
            started_at TEXT,
            completed_at TEXT
        )
    ''')

    # Welcoming & Community
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS welcoming_settings (
            guild_id INTEGER PRIMARY KEY,
            welcome_channel_id INTEGER,
            farewell_channel_id INTEGER,
            auto_role_id INTEGER,
            welcome_msg TEXT,
            farewell_msg TEXT
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            prize TEXT NOT NULL,
            winners INTEGER NOT NULL DEFAULT 1,
            entries TEXT NOT NULL DEFAULT '[]',
            role_req INTEGER NOT NULL DEFAULT 0,
            ends_at TEXT NOT NULL,
            ended INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Tracking & Analytics
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS invite_stats (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            total INTEGER DEFAULT 0,
            joins INTEGER DEFAULT 0,
            leaves INTEGER DEFAULT 0,
            fakes INTEGER DEFAULT 0,
            rejoins INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS invite_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            inviter_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            left_at TEXT,
            is_fake INTEGER DEFAULT 0,
            is_rejoin INTEGER DEFAULT 0
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS message_stats (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            all_time INTEGER DEFAULT 0,
            daily INTEGER DEFAULT 0,
            daily_date TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')

    # Integrations
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS mc_live_panels (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            edition TEXT DEFAULT 'java'
        )
    ''')

    # Performance & Lookups Indexes
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_antinuke_logs_guild ON antinuke_logs(guild_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_ticket_meta_guild ON ticket_metadata(guild_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_leaves_guild_user ON leaves(guild_id, user_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_ignored_channels_guild ON ignored_channels(guild_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_staff_logs_guild ON staff_logs(guild_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_invite_records_guild ON invite_records(guild_id, member_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_dm_campaigns_guild ON dm_campaigns(guild_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_sticky_messages_guild ON sticky_messages(guild_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON giveaways(guild_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_ticket_types_guild ON ticket_types(guild_id)')
    await conn.commit()
