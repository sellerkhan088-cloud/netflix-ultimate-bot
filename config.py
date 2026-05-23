"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🔥 NETFLIX ULTIMATE PREMIUM BOT 🔥                      ║
║     Configuration Module                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram API ──
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "0").split(",") if x.strip()]

# ── Web Server ──
WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "http://localhost:8080")

# ── Database ──
DB_NAME = os.environ.get("DB_NAME", "netflix_ultimate.db")

# ── Defaults ──
DEFAULT_DAILY_LIMIT = int(os.environ.get("DEFAULT_DAILY_LIMIT", "10"))
DEFAULT_AUTO_DELETE = int(os.environ.get("DEFAULT_AUTO_DELETE", "300"))
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "0"))

# ── Developer Info ──
DEV_USERNAME = os.environ.get("DEV_USERNAME", "NetflixBotDev")
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "NetflixBotSupport")
UPDATE_CHANNEL = os.environ.get("UPDATE_CHANNEL", "NetflixBotUpdates")

# ── Version ──
BOT_VERSION = "3.0.0 ULTIMATE"
BOT_NAME = "Netflix Premium Bot"

# ── Colors for Terminal ──
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# ── Admin Check ──
def is_admin(user_id):
    return user_id in ADMIN_IDS
