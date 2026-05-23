"""
╔══════════════════════════════════════════════════════════════╗
║     🔥 NETFLIX ULTIMATE BOT - DATABASE MODULE 🔥           ║
╚══════════════════════════════════════════════════════════════╝
"""

import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from config import DB_NAME, DEFAULT_DAILY_LIMIT, DEFAULT_AUTO_DELETE

logger = logging.getLogger("NetflixDB")


class UltimateDatabase:
    """Advanced Database Manager for Netflix Ultimate Bot"""

    def __init__(self):
        self.db_name = DB_NAME
        self.conn = None
        self.cursor = None
        self.lock = asyncio.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database connection and create tables"""
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._insert_defaults()
        logger.info("✅ Database initialized successfully")

    def _create_tables(self):
        """Create all database tables"""
        self.cursor.executescript("""
            -- ═══════════════════════════════════════
            -- USERS TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                language_code TEXT DEFAULT 'en',
                is_premium INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT DEFAULT '',
                ban_date TIMESTAMP DEFAULT NULL,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                daily_count INTEGER DEFAULT 0,
                total_generated INTEGER DEFAULT 0,
                total_checked INTEGER DEFAULT 0,
                total_converted INTEGER DEFAULT 0,
                last_reset_date TEXT DEFAULT '',
                referral_code TEXT DEFAULT '',
                referred_by INTEGER DEFAULT 0,
                credits INTEGER DEFAULT 0,
                vip_level INTEGER DEFAULT 0,
                vip_expiry TIMESTAMP DEFAULT NULL
            );

            -- ═══════════════════════════════════════
            -- ACCOUNTS TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cookie TEXT NOT NULL,
                email TEXT DEFAULT '',
                password TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                country TEXT DEFAULT '',
                plan TEXT DEFAULT 'Premium',
                subscription_status TEXT DEFAULT 'CURRENT_MEMBER',
                screen_type TEXT DEFAULT 'HD',
                profiles_used INTEGER DEFAULT 0,
                max_profiles INTEGER DEFAULT 5,
                is_used INTEGER DEFAULT 0,
                is_valid INTEGER DEFAULT 1,
                is_premium_acc INTEGER DEFAULT 0,
                used_by INTEGER DEFAULT NULL,
                used_date TIMESTAMP DEFAULT NULL,
                added_by INTEGER DEFAULT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP DEFAULT NULL,
                check_count INTEGER DEFAULT 0,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                source TEXT DEFAULT 'manual'
            );

            -- ═══════════════════════════════════════
            -- CHANNELS TABLE (Force Sub)
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE NOT NULL,
                channel_username TEXT DEFAULT '',
                channel_title TEXT DEFAULT '',
                channel_link TEXT DEFAULT '',
                is_required INTEGER DEFAULT 1,
                position INTEGER DEFAULT 0,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- ═══════════════════════════════════════
            -- SETTINGS TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- ═══════════════════════════════════════
            -- LOGIN TOKENS TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS login_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                account_id INTEGER NOT NULL,
                cookie_data TEXT NOT NULL,
                user_id INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_used INTEGER DEFAULT 0,
                used_at TIMESTAMP DEFAULT NULL,
                access_count INTEGER DEFAULT 0,
                last_access TIMESTAMP DEFAULT NULL
            );

            -- ═══════════════════════════════════════
            -- USER STATES TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT DEFAULT 'idle',
                state_data TEXT DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- ═══════════════════════════════════════
            -- BROADCAST TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                content_type TEXT DEFAULT 'text',
                content TEXT,
                total_targets INTEGER DEFAULT 0,
                sent_success INTEGER DEFAULT 0,
                sent_failed INTEGER DEFAULT 0,
                is_completed INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP DEFAULT NULL
            );

            -- ═══════════════════════════════════════
            -- ANALYTICS TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER DEFAULT NULL,
                data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- ═══════════════════════════════════════
            -- CATEGORIES TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                emoji TEXT DEFAULT '📁',
                description TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                position INTEGER DEFAULT 0
            );

            -- ═══════════════════════════════════════
            -- VIP PLANS TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS vip_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER DEFAULT 0,
                duration_days INTEGER DEFAULT 30,
                daily_limit INTEGER DEFAULT 20,
                features TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1
            );

            -- ═══════════════════════════════════════
            -- BLACKLIST TABLE
            -- ═══════════════════════════════════════
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                reason TEXT DEFAULT '',
                blacklisted_by INTEGER DEFAULT NULL,
                blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
            CREATE INDEX IF NOT EXISTS idx_accounts_valid ON accounts(is_valid, is_used);
            CREATE INDEX IF NOT EXISTS idx_tokens_expires ON login_tokens(expires_at);
            CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics(event_type);
            CREATE INDEX IF NOT EXISTS idx_analytics_date ON analytics(created_at);
        """)
        self.conn.commit()

    def _insert_defaults(self):
        """Insert default settings"""
        defaults = {
            'bot_status': ('1', 'Bot online/offline status'),
            'maintenance_message': ('🔧 Bot is under maintenance. Please try again later.', 'Maintenance message'),
            'welcome_message': ('🎬 Welcome to Netflix Premium Bot!\nGet unlimited Netflix cookies & direct login links instantly! 🚀', 'Welcome message'),
            'daily_limit': (str(DEFAULT_DAILY_LIMIT), 'Daily generation limit per user'),
            'auto_delete': (str(DEFAULT_AUTO_DELETE), 'Auto-delete messages in seconds'),
            'force_sub_enabled': ('1', 'Force subscription enabled'),
            'log_channel': (str(LOG_CHANNEL_ID), 'Log channel ID'),
            'generate_cooldown': ('10', 'Cooldown between generations in seconds'),
            'max_file_size': ('5242880', 'Max file upload size in bytes (5MB)'),
            'max_cookies_per_file': ('500', 'Max cookies per file upload'),
            'token_expiry_hours': ('48', 'Login token expiry in hours'),
            'check_timeout': ('15', 'Cookie check timeout in seconds'),
            'welcome_image': ('', 'Welcome message image URL'),
            'bot_logo': ('', 'Bot logo image URL'),
            'announcements': ('', 'Current announcement text'),
            'referral_enabled': ('0', 'Referral system enabled'),
            'referral_bonus': ('2', 'Extra generations per referral'),
            'vip_enabled': ('0', 'VIP system enabled'),
            'stats_public': ('1', 'Public stats visible'),
            'auto_validate': ('0', 'Auto-validate new cookies'),
            'notification_enabled': ('1', 'Admin notifications'),
            'backup_interval': ('24', 'Backup interval in hours'),
            'theme_color': ('E50914', 'Netflix red theme color'),
        }
        for key, (value, desc) in defaults.items():
            self.cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)",
                (key, value, desc)
            )

        # Default categories
        default_cats = [
            ('Premium 4K', '👑', '4K Ultra HD Premium Accounts', 1),
            ('Premium HD', '💎', 'HD Premium Accounts', 2),
            ('Standard', '⭐', 'Standard Plan Accounts', 3),
            ('Basic', '📱', 'Basic Plan Accounts', 4),
            ('Mobile', '📲', 'Mobile Only Plans', 5),
            ('With Ads', '📺', 'Ad-supported Plans', 6),
            ('General', '📁', 'Mixed General Accounts', 7),
        ]
        for name, emoji, desc, pos in default_cats:
            try:
                self.cursor.execute(
                    "INSERT OR IGNORE INTO categories (name, emoji, description, position) VALUES (?, ?, ?, ?)",
                    (name, emoji, desc, pos)
                )
            except:
                pass

        # Default VIP plans
        default_plans = [
            ('Bronze', 0, 7, 15, 'Daily limit: 15, 7 days access', 1),
            ('Silver', 0, 30, 25, 'Daily limit: 25, 30 days access', 1),
            ('Gold', 0, 30, 50, 'Daily limit: 50, Priority access, 30 days', 1),
            ('Diamond', 0, 90, 999, 'Unlimited, Priority, 90 days', 1),
        ]
        for name, price, dur, limit, feat, active in default_plans:
            try:
                self.cursor.execute(
                    "INSERT OR IGNORE INTO vip_plans (name, price, duration_days, daily_limit, features, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, price, dur, limit, feat, active)
                )
            except:
                pass

        self.conn.commit()

    # ════════════════════════════════════════════════════
    # USER OPERATIONS
    # ════════════════════════════════════════════════════

    def register_user(self, user_id, username="", first_name="", last_name="",
                      language_code="en", is_premium=0, referred_by=0):
        """Register or update a user"""
        existing = self.cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not existing:
            import random
            import string
            ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            self.cursor.execute("""
                INSERT INTO users (user_id, username, first_name, last_name,
                                   language_code, is_premium, referral_code, referred_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, language_code, is_premium, ref_code, referred_by))
            self.conn.commit()
            return True  # New user
        else:
            self.cursor.execute("""
                UPDATE users SET username = ?, first_name = ?, last_name = ?,
                                 language_code = ?, is_premium = ?,
                                 last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (username, first_name, last_name, language_code, is_premium, user_id))
            self.conn.commit()
            return False  # Existing user

    def get_user(self, user_id):
        """Get user data"""
        return self.cursor.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

    def get_all_users(self, limit=None, offset=0):
        """Get all users"""
        if limit:
            return self.cursor.execute(
                "SELECT * FROM users ORDER BY joined_date DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return self.cursor.execute("SELECT * FROM users").fetchall()

    def get_user_count(self):
        """Get total user count"""
        return self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_active_user_count(self, days=7):
        """Get recently active users count"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return self.cursor.execute(
            "SELECT COUNT(*) FROM users WHERE last_active > ?", (cutoff,)
        ).fetchone()[0]

    def ban_user(self, user_id, reason="Violation of terms"):
        """Ban a user"""
        self.cursor.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ?, ban_date = CURRENT_TIMESTAMP WHERE user_id = ?",
            (reason, user_id)
        )
        # Also add to blacklist
        try:
            self.cursor.execute(
                "INSERT OR REPLACE INTO blacklist (user_id, reason) VALUES (?, ?)",
                (user_id, reason)
            )
        except:
            pass
        self.conn.commit()

    def unban_user(self, user_id):
        """Unban a user"""
        self.cursor.execute(
            "UPDATE users SET is_banned = 0, ban_reason = '', ban_date = NULL WHERE user_id = ?",
            (user_id,)
        )
        self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def is_banned(self, user_id):
        """Check if user is banned"""
        r = self.cursor.execute(
            "SELECT is_banned FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return r and r['is_banned'] == 1

    def update_daily_usage(self, user_id):
        """Update daily usage count for a user"""
        today = datetime.now().strftime('%Y-%m-%d')
        user = self.get_user(user_id)
        if user:
            if str(user['last_reset_date']) != today:
                self.cursor.execute(
                    "UPDATE users SET daily_count = 1, last_reset_date = ?, total_generated = total_generated + 1 WHERE user_id = ?",
                    (today, user_id)
                )
            else:
                self.cursor.execute(
                    "UPDATE users SET daily_count = daily_count + 1, total_generated = total_generated + 1 WHERE user_id = ?",
                    (user_id,)
                )
            self.conn.commit()

    def get_daily_count(self, user_id):
        """Get today's usage count for a user"""
        today = datetime.now().strftime('%Y-%m-%d')
        user = self.get_user(user_id)
        if user:
            if str(user['last_reset_date']) != today:
                self.cursor.execute(
                    "UPDATE users SET daily_count = 0, last_reset_date = ? WHERE user_id = ?",
                    (today, user_id)
                )
                self.conn.commit()
                return 0
            return user['daily_count']
        return 0

    def get_user_daily_limit(self, user_id):
        """Get daily limit for a user (considering VIP status)"""
        user = self.get_user(user_id)
        if not user:
            return int(self.get_setting('daily_limit'))

        # VIP users get higher limits
        if user['vip_level'] > 0 and user['vip_expiry']:
            if datetime.now() < datetime.fromisoformat(user['vip_expiry']):
                plan = self.cursor.execute(
                    "SELECT daily_limit FROM vip_plans WHERE id = ?", (user['vip_level'],)
                ).fetchone()
                if plan:
                    return plan['daily_limit']
            else:
                # VIP expired
                self.cursor.execute(
                    "UPDATE users SET vip_level = 0, vip_expiry = NULL WHERE user_id = ?",
                    (user_id,)
                )
                self.conn.commit()

        return int(self.get_setting('daily_limit'))

    def search_users(self, query):
        """Search users by ID, username, or name"""
        return self.cursor.execute(
            """SELECT * FROM users WHERE 
               CAST(user_id AS TEXT) LIKE ? OR 
               username LIKE ? OR 
               first_name LIKE ?""",
            (f'%{query}%', f'%{query}%', f'%{query}%')
        ).fetchall()

    # ════════════════════════════════════════════════════
    # ACCOUNT OPERATIONS
    # ════════════════════════════════════════════════════

    def add_account(self, cookie, email="", password="", phone="", country="",
                    plan="Premium", status="CURRENT_MEMBER", screen_type="HD",
                    added_by=None, category="general", source="manual", notes=""):
        """Add a new account"""
        self.cursor.execute("""
            INSERT INTO accounts (cookie, email, password, phone, country, plan,
                                  subscription_status, screen_type, added_by,
                                  category, source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cookie, email, password, phone, country, plan, status,
              screen_type, added_by, category, source, notes))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_account(self, account_id):
        """Get account by ID"""
        return self.cursor.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()

    def get_available_account(self, category=None):
        """Get a random available account"""
        if category and category != "all":
            self.cursor.execute(
                """SELECT * FROM accounts 
                   WHERE is_used = 0 AND is_valid = 1 AND category = ?
                   ORDER BY RANDOM() LIMIT 1""",
                (category,)
            )
        else:
            self.cursor.execute(
                """SELECT * FROM accounts 
                   WHERE is_used = 0 AND is_valid = 1
                   ORDER BY RANDOM() LIMIT 1"""
            )
        return self.cursor.fetchone()

    def mark_account_used(self, account_id, used_by):
        """Mark an account as used"""
        self.cursor.execute(
            "UPDATE accounts SET is_used = 1, used_by = ?, used_date = CURRENT_TIMESTAMP WHERE id = ?",
            (used_by, account_id)
        )
        self.conn.commit()

    def reset_account(self, account_id):
        """Reset an account to available"""
        self.cursor.execute(
            "UPDATE accounts SET is_used = 0, used_by = NULL, used_date = NULL WHERE id = ?",
            (account_id,)
        )
        self.conn.commit()

    def delete_account(self, account_id):
        """Delete an account"""
        self.cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()

    def invalidate_account(self, account_id):
        """Mark account as invalid"""
        self.cursor.execute(
            "UPDATE accounts SET is_valid = 0 WHERE id = ?", (account_id,)
        )
        self.conn.commit()

    def validate_account(self, account_id):
        """Mark account as valid"""
        self.cursor.execute(
            "UPDATE accounts SET is_valid = 1 WHERE id = ?", (account_id,)
        )
        self.conn.commit()

    def update_account_check(self, account_id, is_valid):
        """Update account after validity check"""
        self.cursor.execute(
            "UPDATE accounts SET is_valid = ?, last_checked = CURRENT_TIMESTAMP, check_count = check_count + 1 WHERE id = ?",
            (1 if is_valid else 0, account_id)
        )
        self.conn.commit()

    def get_accounts(self, limit=10, offset=0, category=None, status=None):
        """Get accounts with filters"""
        query = "SELECT * FROM accounts WHERE 1=1"
        params = []
        if category and category != "all":
            query += " AND category = ?"
            params.append(category)
        if status == "available":
            query += " AND is_used = 0 AND is_valid = 1"
        elif status == "used":
            query += " AND is_used = 1"
        elif status == "invalid":
            query += " AND is_valid = 0"
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self.cursor.execute(query, params).fetchall()

    def get_account_count(self, status=None):
        """Get account count by status"""
        if status == "available":
            return self.cursor.execute(
                "SELECT COUNT(*) FROM accounts WHERE is_used = 0 AND is_valid = 1"
            ).fetchone()[0]
        elif status == "used":
            return self.cursor.execute(
                "SELECT COUNT(*) FROM accounts WHERE is_used = 1"
            ).fetchone()[0]
        elif status == "invalid":
            return self.cursor.execute(
                "SELECT COUNT(*) FROM accounts WHERE is_valid = 0"
            ).fetchone()[0]
        return self.cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]

    def search_accounts(self, query):
        """Search accounts"""
        return self.cursor.execute(
            """SELECT * FROM accounts WHERE
               email LIKE ? OR phone LIKE ? OR country LIKE ? OR
               cookie LIKE ? OR category LIKE ?""",
            (f'%{query}%', f'%{query}%', f'%{query}%',
             f'%{query}%', f'%{query}%')
        ).fetchall()

    def clean_used_accounts(self):
        """Delete all used accounts"""
        count = self.get_account_count("used")
        self.cursor.execute("DELETE FROM accounts WHERE is_used = 1")
        self.conn.commit()
        return count

    def clean_invalid_accounts(self):
        """Delete all invalid accounts"""
        count = self.get_account_count("invalid")
        self.cursor.execute("DELETE FROM accounts WHERE is_valid = 0")
        self.conn.commit()
        return count

    def reset_all_used(self):
        """Reset all used accounts"""
        count = self.get_account_count("used")
        self.cursor.execute(
            "UPDATE accounts SET is_used = 0, used_by = NULL, used_date = NULL WHERE is_used = 1"
        )
        self.conn.commit()
        return count

    def get_category_stats(self):
        """Get account counts by category"""
        return self.cursor.execute(
            """SELECT category, 
                      COUNT(*) as total,
                      SUM(CASE WHEN is_used = 0 AND is_valid = 1 THEN 1 ELSE 0 END) as available,
                      SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as used,
                      SUM(CASE WHEN is_valid = 0 THEN 1 ELSE 0 END) as invalid
               FROM accounts GROUP BY category"""
        ).fetchall()

    def get_country_stats(self):
        """Get account counts by country"""
        return self.cursor.execute(
            """SELECT country, COUNT(*) as count,
                      SUM(CASE WHEN is_used = 0 AND is_valid = 1 THEN 1 ELSE 0 END) as available
               FROM accounts WHERE country != '' GROUP BY country ORDER BY count DESC LIMIT 20"""
        ).fetchall()

    # ════════════════════════════════════════════════════
    # CHANNEL OPERATIONS
    # ════════════════════════════════════════════════════

    def add_channel(self, channel_id, channel_username="", channel_title="", channel_link=""):
        """Add a force-sub channel"""
        try:
            self.cursor.execute(
                "INSERT INTO channels (channel_id, channel_username, channel_title, channel_link) VALUES (?, ?, ?, ?)",
                (channel_id, channel_username, channel_title, channel_link)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_channel(self, channel_id):
        """Remove a force-sub channel"""
        self.cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        self.conn.commit()

    def get_all_channels(self):
        """Get all required channels"""
        return self.cursor.execute(
            "SELECT * FROM channels WHERE is_required = 1 ORDER BY position"
        ).fetchall()

    def get_channel_count(self):
        """Get required channels count"""
        return self.cursor.execute(
            "SELECT COUNT(*) FROM channels WHERE is_required = 1"
        ).fetchone()[0]

    # ════════════════════════════════════════════════════
    # SETTINGS OPERATIONS
    # ════════════════════════════════════════════════════

    def get_setting(self, key, default=None):
        """Get a setting value"""
        r = self.cursor.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return r['value'] if r else default

    def set_setting(self, key, value):
        """Set a setting value"""
        self.cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value)
        )
        self.conn.commit()

    def get_all_settings(self):
        """Get all settings"""
        return self.cursor.execute(
            "SELECT * FROM settings ORDER BY key"
        ).fetchall()

    # ════════════════════════════════════════════════════
    # LOGIN TOKEN OPERATIONS
    # ════════════════════════════════════════════════════

    def create_login_token(self, account_id, cookie_data, user_id=None, hours=None):
        """Create a login token"""
        import hashlib
        import time
        import random
        token = hashlib.sha256(
            f"{account_id}{time.time()}{random.random()}".encode()
        ).hexdigest()[:48]
        expiry_hours = hours or int(self.get_setting('token_expiry_hours', '48'))
        expires_at = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
        self.cursor.execute(
            "INSERT INTO login_tokens (token, account_id, cookie_data, user_id, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token, account_id, cookie_data, user_id, expires_at)
        )
        self.conn.commit()
        return token

    def get_login_token(self, token):
        """Get a valid login token"""
        return self.cursor.execute(
            """SELECT * FROM login_tokens 
               WHERE token = ? AND is_used = 0 AND expires_at > ?""",
            (token, datetime.now().isoformat())
        ).fetchone()

    def mark_token_used(self, token):
        """Mark a token as used"""
        self.cursor.execute(
            "UPDATE login_tokens SET is_used = 1, used_at = CURRENT_TIMESTAMP WHERE token = ?",
            (token,)
        )
        self.conn.commit()

    def increment_token_access(self, token):
        """Increment token access count"""
        self.cursor.execute(
            "UPDATE login_tokens SET access_count = access_count + 1, last_access = CURRENT_TIMESTAMP WHERE token = ?",
            (token,)
        )
        self.conn.commit()

    def cleanup_expired_tokens(self):
        """Delete expired tokens"""
        count = self.cursor.execute(
            "SELECT COUNT(*) FROM login_tokens WHERE expires_at < ?",
            (datetime.now().isoformat(),)
        ).fetchone()[0]
        self.cursor.execute(
            "DELETE FROM login_tokens WHERE expires_at < ?",
            (datetime.now().isoformat(),)
        )
        self.conn.commit()
        return count

    # ════════════════════════════════════════════════════
    # USER STATE OPERATIONS
    # ════════════════════════════════════════════════════

    def set_user_state(self, user_id, state, state_data="{}"):
        """Set user's current state"""
        self.cursor.execute(
            "INSERT OR REPLACE INTO user_states (user_id, state, state_data, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (user_id, state, state_data)
        )
        self.conn.commit()

    def get_user_state(self, user_id):
        """Get user's current state"""
        r = self.cursor.execute(
            "SELECT state, state_data FROM user_states WHERE user_id = ?", (user_id,)
        ).fetchone()
        return (r['state'], r['state_data']) if r else ('idle', '{}')

    def clear_user_state(self, user_id):
        """Clear user's state"""
        self.cursor.execute(
            "UPDATE user_states SET state = 'idle', state_data = '{}' WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()

    # ════════════════════════════════════════════════════
    # ANALYTICS OPERATIONS
    # ════════════════════════════════════════════════════

    def log_event(self, event_type, user_id=None, data="{}"):
        """Log an analytics event"""
        self.cursor.execute(
            "INSERT INTO analytics (event_type, user_id, data) VALUES (?, ?, ?)",
            (event_type, user_id, data)
        )
        self.conn.commit()

    def get_event_count(self, event_type, hours=24):
        """Get event count in last N hours"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        return self.cursor.execute(
            "SELECT COUNT(*) FROM analytics WHERE event_type = ? AND created_at > ?",
            (event_type, cutoff)
        ).fetchone()[0]

    def get_total_generated_today(self):
        """Get total generations today"""
        today = datetime.now().strftime('%Y-%m-%d')
        r = self.cursor.execute(
            "SELECT SUM(daily_count) FROM users WHERE last_reset_date = ?", (today,)
        ).fetchone()[0]
        return r or 0

    # ════════════════════════════════════════════════════
    # CATEGORY OPERATIONS
    # ════════════════════════════════════════════════════

    def get_categories(self):
        """Get all active categories"""
        return self.cursor.execute(
            "SELECT * FROM categories WHERE is_active = 1 ORDER BY position"
        ).fetchall()

    def add_category(self, name, emoji="📁", description=""):
        """Add a new category"""
        try:
            pos = self.cursor.execute("SELECT MAX(position) FROM categories").fetchone()[0] or 0
            self.cursor.execute(
                "INSERT INTO categories (name, emoji, description, position) VALUES (?, ?, ?, ?)",
                (name, emoji, description, pos + 1)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_category(self, name):
        """Delete a category"""
        self.cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
        self.conn.commit()

    # ════════════════════════════════════════════════════
    # EXPORT OPERATIONS
    # ════════════════════════════════════════════════════

    def export_users_csv(self):
        """Export users data as CSV"""
        users = self.get_all_users()
        if not users:
            return None
        lines = ["user_id,username,first_name,is_banned,total_generated,daily_count,joined_date,last_active"]
        for u in users:
            lines.append(f"{u['user_id']},{u['username']},{u['first_name']},{u['is_banned']},{u['total_generated']},{u['daily_count']},{u['joined_date']},{u['last_active']}")
        return "\n".join(lines)

    def export_accounts_txt(self, status_filter=None):
        """Export accounts as text"""
        accounts = self.get_accounts(limit=10000, offset=0, status=status_filter)
        if not accounts:
            return None
        lines = []
        for a in accounts:
            line = a['cookie']
            if a['email']:
                line += f"|{a['email']}"
            if a['phone']:
                line += f"|{a['phone']}"
            if a['country']:
                line += f"|{a['country']}"
            if a['plan']:
                line += f"|{a['plan']}"
            lines.append(line)
        return "\n".join(lines)

    # ════════════════════════════════════════════════════
    # BACKUP & RESTORE
    # ════════════════════════════════════════════════════

    def get_stats_summary(self):
        """Get comprehensive stats"""
        total_users = self.get_user_count()
        active_users = self.get_active_user_count(7)
        banned_users = self.cursor.execute(
            "SELECT COUNT(*) FROM users WHERE is_banned = 1"
        ).fetchone()[0]

        total_accounts = self.get_account_count()
        available = self.get_account_count("available")
        used = self.get_account_count("used")
        invalid = self.get_account_count("invalid")

        today_gen = self.get_total_generated_today()
        channels = self.get_channel_count()

        return {
            'total_users': total_users,
            'active_users': active_users,
            'banned_users': banned_users,
            'total_accounts': total_accounts,
            'available_accounts': available,
            'used_accounts': used,
            'invalid_accounts': invalid,
            'today_generated': today_gen,
            'channels': channels,
        }
