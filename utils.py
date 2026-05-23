"""
╔══════════════════════════════════════════════════════════════╗
║     🔥 NETFLIX ULTIMATE BOT - UTILITIES MODULE 🔥          ║
╚══════════════════════════════════════════════════════════════╝
"""

import re
import time
import hashlib
import random
import asyncio
import logging
from datetime import datetime, timedelta
from io import BytesIO

import aiohttp
from pyrogram import enums

from config import WEB_BASE_URL

logger = logging.getLogger("NetflixUtils")


# ════════════════════════════════════════════════════
# PROGRESS BAR
# ════════════════════════════════════════════════════

def progress_bar(current, total, length=12, fill="█", empty="░"):
    """Create a visual progress bar"""
    if total <= 0:
        return empty * length
    filled = int(length * current / total)
    if filled > length:
        filled = length
    return fill * filled + empty * (length - filled)


def percentage_bar(current, total):
    """Create progress bar with percentage"""
    if total <= 0:
        pct = 0
    else:
        pct = int((current / total) * 100)
    bar = progress_bar(current, total)
    return f"{bar} {pct}%"


# ════════════════════════════════════════════════════
# COOKIE UTILITIES
# ════════════════════════════════════════════════════

def parse_cookie_line(line):
    """Parse a cookie line with pipe-separated metadata
    
    Format: cookie|email|phone|country|plan|status|screen_type
    Returns: dict with parsed data
    """
    parts = line.strip().split('|')
    cookie = parts[0].strip() if parts else ""

    result = {
        'cookie': cookie,
        'email': parts[1].strip() if len(parts) > 1 else "",
        'phone': parts[2].strip() if len(parts) > 2 else "",
        'country': parts[3].strip() if len(parts) > 3 else "",
        'plan': parts[4].strip() if len(parts) > 4 else "Premium",
        'status': parts[5].strip() if len(parts) > 5 else "CURRENT_MEMBER",
        'screen_type': parts[6].strip() if len(parts) > 6 else "HD",
        'category': parts[7].strip() if len(parts) > 7 else "general",
    }
    return result


def is_valid_cookie_format(cookie_string):
    """Basic validation of cookie string format"""
    if not cookie_string or len(cookie_string) < 20:
        return False
    # Netflix cookies typically contain certain patterns
    netflix_patterns = [
        'NetflixId',
        'nfSessionId',
        'Netflix',
        'netflix',
        'Auth',
        'token',
        'session',
    ]
    cookie_lower = cookie_string.lower()
    return any(p.lower() in cookie_lower for p in netflix_patterns)


async def check_netflix_cookie(cookie_string, timeout=15):
    """Check if a Netflix cookie is still valid"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': cookie_string,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://www.netflix.com/browse',
                headers=headers,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status in [301, 302, 303, 307, 308]:
                    location = resp.headers.get('Location', '')
                    if 'login' in location.lower():
                        return False, "Redirected to login page"
                    return True, "Active (redirect)"
                elif resp.status == 200:
                    text = await resp.text()
                    if 'login' in text.lower() and 'password' in text.lower():
                        return False, "Login page content detected"
                    if 'shakti' in text.lower() or 'browse' in text.lower():
                        return True, "Active account detected"
                    return True, "Valid response"
                elif resp.status == 403:
                    return False, "Access forbidden (cookie expired)"
                else:
                    return None, f"Unknown status: {resp.status}"
    except asyncio.TimeoutError:
        return None, "Request timed out"
    except aiohttp.ClientError as e:
        return None, f"Network error: {str(e)[:50]}"
    except Exception as e:
        logger.error(f"Cookie check error: {e}")
        return None, f"Error: {str(e)[:50]}"


# ════════════════════════════════════════════════════
# FORMAT HELPERS
# ════════════════════════════════════════════════════

def format_account_info(account, include_cookie=True, short_cookie=True):
    """Format account information for display"""
    if account['is_used']:
        status_emoji = "🔴"
        status_text = "Used"
    elif not account['is_valid']:
        status_emoji = "⚠️"
        status_text = "Invalid"
    else:
        status_emoji = "✅"
        status_text = "Available"

    plan_emoji = {
        'Premium': '👑',
        'Standard': '⭐',
        'Basic': '📱',
        'Mobile': '📲',
        'With Ads': '📺',
    }.get(account['plan'], '🎬')

    text = (
        f"✅ <b>Netflix Account Found!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📧 <b>Email:</b> <code>{account['email'] or 'Not Available'}</code>\n"
        f"📱 <b>Phone:</b> <code>{account['phone'] or 'Not Available'}</code>\n"
        f"🌍 <b>Country:</b> {account['country'] or 'Unknown'}\n"
        f"📋 <b>Plan:</b> {plan_emoji} {account['plan'] or 'Premium'}\n"
        f"📊 <b>Status:</b> {account['subscription_status'] or 'CURRENT_MEMBER'}\n"
        f"🖥️ <b>Screen:</b> {account['screen_type'] or 'HD'}\n"
        f"🔑 <b>Account Status:</b> {status_emoji} {status_text}\n"
    )
    if include_cookie:
        cookie = account['cookie']
        if short_cookie and len(cookie) > 150:
            cookie = cookie[:150] + "..."
        text += f"\n🍪 <b>Cookie:</b>\n<code>{cookie}</code>"
    return text


def format_time_ago(dt_string):
    """Format a datetime string as 'time ago'"""
    if not dt_string:
        return "Never"
    try:
        dt = datetime.fromisoformat(str(dt_string))
        diff = datetime.now() - dt
        if diff.days > 365:
            return f"{diff.days // 365}y ago"
        if diff.days > 30:
            return f"{diff.days // 30}mo ago"
        if diff.days > 0:
            return f"{diff.days}d ago"
        if diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        if diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        return "Just now"
    except:
        return str(dt_string)


def format_number(n):
    """Format large numbers with K, M suffixes"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def create_login_link(token):
    """Create login URL from token"""
    return f"{WEB_BASE_URL}/login/{token}"


# ════════════════════════════════════════════════════
# KEYBOARD BUILDERS
# ════════════════════════════════════════════════════

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb(categories=None):
    """Build main menu keyboard"""
    buttons = [
        [InlineKeyboardButton("🔑 Generate Now", callback_data="gen_now")]
    ]
    
    # Category selection
    if categories:
        cat_row = []
        for cat in categories[:3]:  # Max 3 per row
            cat_row.append(InlineKeyboardButton(
                f"{cat['emoji']} {cat['name']}", 
                callback_data=f"gen_cat_{cat['name'].lower().replace(' ', '_')}"
            ))
        if cat_row:
            buttons.append(cat_row)
        
        # More categories
        if len(categories) > 3:
            cat_row2 = []
            for cat in categories[3:6]:
                cat_row2.append(InlineKeyboardButton(
                    f"{cat['emoji']} {cat['name']}",
                    callback_data=f"gen_cat_{cat['name'].lower().replace(' ', '_')}"
                ))
            if cat_row2:
                buttons.append(cat_row2)

    buttons.extend([
        [
            InlineKeyboardButton("📄 Send File .txt", callback_data="send_file"),
            InlineKeyboardButton("💬 Send Text", callback_data="send_text")
        ],
        [
            InlineKeyboardButton("🔍 Check Cookie", callback_data="check_cookie"),
            InlineKeyboardButton("📊 My Stats", callback_data="my_stats")
        ],
        [
            InlineKeyboardButton("📖 How to Use", callback_data="how_use"),
            InlineKeyboardButton("💎 About", callback_data="about")
        ]
    ])
    return InlineKeyboardMarkup(buttons)


def admin_panel_kb():
    """Build admin panel keyboard"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Dashboard Stats", callback_data="adm_stats")],
        [
            InlineKeyboardButton("➕ Add Account", callback_data="adm_add_acc"),
            InlineKeyboardButton("📁 Bulk Upload", callback_data="adm_upload")
        ],
        [
            InlineKeyboardButton("📋 All Accounts", callback_data="adm_acc_list_0_all"),
            InlineKeyboardButton("🔍 Search", callback_data="adm_search")
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
            InlineKeyboardButton("👥 Users", callback_data="adm_users_0")
        ],
        [
            InlineKeyboardButton("🚫 Ban User", callback_data="adm_ban"),
            InlineKeyboardButton("✅ Unban User", callback_data="adm_unban")
        ],
        [
            InlineKeyboardButton("📺 Add Channel", callback_data="adm_add_ch"),
            InlineKeyboardButton("📺 Channels", callback_data="adm_channels")
        ],
        [
            InlineKeyboardButton("📁 Categories", callback_data="adm_categories"),
            InlineKeyboardButton("🏷️ VIP Plans", callback_data="adm_vip")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="adm_settings"),
            InlineKeyboardButton("🔧 Maintenance", callback_data="adm_maint")
        ],
        [
            InlineKeyboardButton("🧹 Clean Used", callback_data="adm_clean_used"),
            InlineKeyboardButton("🗑️ Clean Invalid", callback_data="adm_clean_invalid")
        ],
        [
            InlineKeyboardButton("🔄 Reset All Used", callback_data="adm_reset_all"),
            InlineKeyboardButton("🔍 Bulk Check", callback_data="adm_bulk_check")
        ],
        [
            InlineKeyboardButton("📤 Export Data", callback_data="adm_export"),
            InlineKeyboardButton("📈 Analytics", callback_data="adm_analytics")
        ],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
    ])


def cancel_kb():
    """Cancel action keyboard"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
    ])


def back_kb(target="back_main", text="🔙 Back"):
    """Simple back button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=target)]
    ])


def admin_back_kb():
    """Back to admin panel"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")]
    ])


def pagination_kb(current_page, total_pages, prefix, extra_buttons=None):
    """Build pagination keyboard"""
    buttons = []
    nav = []
    if current_page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_{current_page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {current_page + 1}/{total_pages}", callback_data="noop"))
    if current_page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}_{current_page + 1}"))
    buttons.append(nav)
    if extra_buttons:
        buttons.extend(extra_buttons)
    return InlineKeyboardMarkup(buttons)
