"""
╔════════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     🔥🔥🔥 NETFLIX ULTIMATE PREMIUM BOT 🔥🔥🔥                     ║
║                                                                      ║
║     ✨ Unlimited Cookie Generation, Login & Check Method ✨          ║
║     🎨 Beautiful UI with Colorful Buttons                           ║
║     🔐 Full Admin Control Panel                                     ║
║     📊 Advanced Analytics & Statistics                              ║
║     🛡️ VIP System, Categories, Referral System                      ║
║     🌐 Web Server for Direct Login Links                            ║
║                                                                      ║
║     Version: 3.0.0 ULTIMATE                                         ║
║                                                                      ║
╚════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import random
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from io import BytesIO

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, Message, InputMediaPhoto
)
from pyrogram.errors import (
    UserNotParticipant, FloodWait, BadRequest,
    MessageNotModified, MessageDeleteForbidden
)

from config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS,
    WEB_BASE_URL, WEB_HOST, WEB_PORT, BOT_VERSION, BOT_NAME,
    DEV_USERNAME, SUPPORT_CHAT, UPDATE_CHANNEL, is_admin
)
from database import UltimateDatabase
from utils import (
    progress_bar, percentage_bar, parse_cookie_line, is_valid_cookie_format,
    check_netflix_cookie, format_account_info, format_time_ago, format_number,
    create_login_link, main_menu_kb, admin_panel_kb, cancel_kb, back_kb,
    admin_back_kb, pagination_kb
)
from web_server import WebServer

# ════════════════════════════════════════════════════
# LOGGING SETUP
# ════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s │ %(name)-18s │ %(levelname)-8s │ %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("netflix_bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("NetflixBot")

# ════════════════════════════════════════════════════
# INITIALIZE
# ════════════════════════════════════════════════════

db = UltimateDatabase()

app = Client(
    "NetflixUltimateBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# User cooldown tracking
user_cooldowns = {}

# ════════════════════════════════════════════════════
# START WEB SERVER IN BACKGROUND
# ════════════════════════════════════════════════════

def start_web_server():
    """Start web server in a separate thread"""
    server = WebServer(db)
    web.run_app(server.app, host=WEB_HOST, port=WEB_PORT, print=None)

# ════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════

async def check_force_sub(user_id):
    """Check if user has joined all required channels"""
    channels = db.get_all_channels()
    if not channels:
        return True, []

    if db.get_setting('force_sub_enabled') != '1':
        return True, []

    not_joined = []
    for ch in channels:
        try:
            member = await app.get_chat_member(ch['channel_id'], user_id)
            if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
                not_joined.append(ch)
        except Exception as e:
            logger.warning(f"Channel check error for {ch['channel_id']}: {e}")
            not_joined.append(ch)

    return len(not_joined) == 0, not_joined


def check_cooldown(user_id, action="generate"):
    """Check if user is on cooldown"""
    key = f"{user_id}_{action}"
    if key in user_cooldowns:
        remaining = user_cooldowns[key] - time.time()
        if remaining > 0:
            return int(remaining)
    return 0


def set_cooldown(user_id, action="generate", seconds=10):
    """Set cooldown for user action"""
    key = f"{user_id}_{action}"
    user_cooldowns[key] = time.time() + seconds


async def log_to_channel(text, account_info=None):
    """Log event to log channel"""
    log_ch = int(db.get_setting('log_channel', '0'))
    if not log_ch or log_ch == 0:
        return
    try:
        await app.send_message(log_ch, text, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        logger.error(f"Log channel error: {e}")


def build_welcome_text(user, fname):
    """Build welcome message text"""
    uid = user['user_id']
    welcome = db.get_setting('welcome_message', '')
    avail = db.get_account_count('available')
    total_users = db.get_user_count()
    limit = db.get_user_daily_limit(uid)
    used = db.get_daily_count(uid)

    announcement = db.get_setting('announcements', '')
    announcement_text = ""
    if announcement:
        announcement_text = f"\n📢 <b>Announcement:</b>\n{announcement}\n━━━━━━━━━━━━━━━━━━━━━━\n"

    vip_text = ""
    if user['vip_level'] > 0:
        vip_text = f"👑 <b>VIP Level:</b> {user['vip_level']}\n"

    return (
        f"🎬 <b>Welcome to {BOT_NAME}!</b> 🔥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{announcement_text}"
        f"{welcome}\n\n"
        f"👤 <b>User:</b> <a href='tg://user?id={uid}'>{fname}</a>\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"{vip_text}"
        f"📦 <b>Available Accounts:</b> {format_number(avail)}\n"
        f"📝 <b>Today's Usage:</b> {used}/{limit}\n"
        f"👥 <b>Total Users:</b> {format_number(total_users)}\n\n"
        f"👇 <b>Choose an option below:</b>"
    )


# ════════════════════════════════════════════════════
# COMMAND: /start
# ════════════════════════════════════════════════════

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client, message: Message):
    uid = message.from_user.id
    uname = message.from_user.username or ""
    fname = message.from_user.first_name or ""
    lname = message.from_user.last_name or ""
    lang = message.from_user.language_code or "en"
    is_prem = 1 if message.from_user.is_premium else 0

    # Check referral
    referred_by = 0
    if len(message.command) > 1:
        try:
            referred_by = int(message.command[1])
        except:
            pass

    # Register user
    is_new = db.register_user(uid, uname, fname, lname, lang, is_prem, referred_by)
    user = db.get_user(uid)

    if is_new:
        db.log_event('new_user', uid, json.dumps({'username': uname}))
        await log_to_channel(
            f"🆕 <b>New User</b>\n\n"
            f"👤 {fname} (@{uname})\n"
            f"🆔 <code>{uid}</code>\n"
            f"👥 Total Users: {db.get_user_count()}"
        )

    # Check ban
    if db.is_banned(uid):
        reason = user['ban_reason'] or "Not specified"
        await message.reply_text(
            f"🚫 <b>You are banned from using this bot!</b>\n\n"
            f"📝 <b>Reason:</b> <code>{reason}</code>\n"
            f"📅 <b>Banned:</b> {format_time_ago(user['ban_date'])}\n\n"
            f"💬 Contact @{SUPPORT_CHAT} for appeal",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Check maintenance
    if db.get_setting('bot_status') != '1' and not is_admin(uid):
        await message.reply_text(
            db.get_setting('maintenance_message', '🔧 Under maintenance.'),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Check force sub
    joined, not_joined = await check_force_sub(uid)
    if not joined:
        buttons = []
        for ch in not_joined:
            link = ch['channel_link'] or (
                f"https://t.me/{ch['channel_username']}" if ch['channel_username']
                else f"https://t.me/c/{abs(ch['channel_id'])}"
            )
            buttons.append([InlineKeyboardButton(
                f"📢 {ch['channel_title'] or 'Join Channel'}", url=link
            )])
        buttons.append([InlineKeyboardButton(
            "✅ I've Joined - Verify Now", callback_data="verify_join"
        )])

        await message.reply_text(
            "🔒 <b>Verification Required!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please join all required channels first to access the bot:\n\n"
            "👇 Join all channels, then tap <b>Verify</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Show main menu
    categories = db.get_categories()
    text = build_welcome_text(user, fname)

    await message.reply_text(
        text,
        reply_markup=main_menu_kb(categories),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


# ════════════════════════════════════════════════════
# CALLBACK: verify_join
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("verify_join"))
async def cb_verify_join(client, cb: CallbackQuery):
    uid = cb.from_user.id
    joined, not_joined = await check_force_sub(uid)

    if joined:
        user = db.get_user(uid)
        fname = cb.from_user.first_name or ""
        categories = db.get_categories()
        text = build_welcome_text(user, fname)

        await cb.message.edit_text(
            text,
            reply_markup=main_menu_kb(categories),
            parse_mode=enums.ParseMode.HTML
        )
        await cb.answer("✅ Verification successful!", show_alert=False)
    else:
        await cb.answer(
            "❌ You haven't joined all channels yet!\n"
            "Please join and try again.",
            show_alert=True
        )


# ════════════════════════════════════════════════════
# CALLBACK: back_main
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("back_main"))
async def cb_back_main(client, cb: CallbackQuery):
    uid = cb.from_user.id
    user = db.get_user(uid)
    if not user:
        return
    fname = cb.from_user.first_name or ""
    categories = db.get_categories()
    text = build_welcome_text(user, fname)

    try:
        await cb.message.edit_text(
            text,
            reply_markup=main_menu_kb(categories),
            parse_mode=enums.ParseMode.HTML
        )
    except MessageNotModified:
        pass


# ════════════════════════════════════════════════════
# CALLBACK: cancel_action
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("cancel_action"))
async def cb_cancel(client, cb: CallbackQuery):
    uid = cb.from_user.id
    db.clear_user_state(uid)
    await cb_back_main(client, cb)
    await cb.answer("❌ Action cancelled!")


# ════════════════════════════════════════════════════
# CALLBACK: noop (for pagination display)
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("noop"))
async def cb_noop(client, cb: CallbackQuery):
    await cb.answer("📄 Page info", show_alert=False)


# ════════════════════════════════════════════════════
# CALLBACK: gen_now - Generate Account
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("gen_now"))
async def cb_generate(client, cb: CallbackQuery):
    uid = cb.from_user.id

    # Checks
    if db.is_banned(uid):
        await cb.answer("🚫 You are banned!", show_alert=True)
        return

    if db.get_setting('bot_status') != '1':
        await cb.answer("🔧 Bot is under maintenance!", show_alert=True)
        return

    joined, _ = await check_force_sub(uid)
    if not joined:
        await cb.answer("❌ Join required channels first!", show_alert=True)
        return

    # Cooldown check
    cd = check_cooldown(uid, "generate")
    if cd > 0:
        await cb.answer(f"⏳ Cooldown! Wait {cd}s", show_alert=True)
        return

    # Daily limit check
    limit = db.get_user_daily_limit(uid)
    used = db.get_daily_count(uid)
    if used >= limit:
        await cb.answer(
            f"⚠️ Daily limit reached! ({used}/{limit})\n"
            f"Try again tomorrow or upgrade to VIP!",
            show_alert=True
        )
        return

    # Get account
    account = db.get_available_account()
    if not account:
        await cb.answer(
            "❌ No accounts available right now!\n"
            "Please try again later.",
            show_alert=True
        )
        return

    # Create login token
    token = db.create_login_token(account['id'], account['cookie'], uid)
    login_link = create_login_link(token)

    # Mark account used
    db.mark_account_used(account['id'], uid)
    db.update_daily_usage(uid)
    db.log_event('generate', uid, json.dumps({'account_id': account['id']}))

    # Set cooldown
    cooldown_sec = int(db.get_setting('generate_cooldown', '10'))
    set_cooldown(uid, "generate", cooldown_sec)

    # Build response
    info = format_account_info(account, include_cookie=True, short_cookie=True)
    auto_del = int(db.get_setting('auto_delete', '300'))
    remaining = limit - used - 1

    response = (
        f"{info}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Direct Login Link:</b>\n"
        f"<code>{login_link}</code>\n\n"
        f"💡 Click link → Copy Cookie → Open Netflix → Done! 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Remaining today:</b> {remaining}/{limit}\n"
        f"⏰ <b>Auto-delete in:</b> {auto_del}s\n"
        f"🎫 <b>Token expires:</b> {db.get_setting('token_expiry_hours', '48')}h"
    )

    msg = await cb.message.edit_text(
        response,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open Login Page", url=login_link)],
            [
                InlineKeyboardButton("📥 Download .txt", callback_data=f"dl_acc_{account['id']}"),
                InlineKeyboardButton("📋 Full Cookie", callback_data=f"full_ck_{account['id']}")
            ],
            [
                InlineKeyboardButton("🔄 Generate Another", callback_data="gen_now"),
                InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")
            ]
        ]),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

    # Log
    await log_to_channel(
        f"📝 <b>Account Generated</b>\n\n"
        f"👤 User: <a href='tg://user?id={uid}'>{cb.from_user.first_name}</a> ({uid})\n"
        f"🆔 Account: #{account['id']}\n"
        f"📧 Email: {account['email'] or 'N/A'}\n"
        f"🌍 Country: {account['country'] or 'N/A'}"
    )

    # Auto-delete
    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass


# ════════════════════════════════════════════════════
# CALLBACK: gen_cat_ - Generate by Category
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"gen_cat_(.+)"))
async def cb_generate_category(client, cb: CallbackQuery):
    uid = cb.from_user.id
    category = cb.matches[0].group(1).replace('_', ' ')

    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return

    # Checks
    limit = db.get_user_daily_limit(uid)
    used = db.get_daily_count(uid)
    if used >= limit:
        await cb.answer(f"⚠️ Daily limit reached! ({used}/{limit})", show_alert=True)
        return

    account = db.get_available_account(category=category)
    if not account:
        await cb.answer(f"❌ No {category} accounts available!", show_alert=True)
        return

    token = db.create_login_token(account['id'], account['cookie'], uid)
    login_link = create_login_link(token)

    db.mark_account_used(account['id'], uid)
    db.update_daily_usage(uid)
    db.log_event('generate', uid, json.dumps({'account_id': account['id'], 'category': category}))

    info = format_account_info(account)
    auto_del = int(db.get_setting('auto_delete', '300'))

    response = (
        f"{info}\n\n"
        f"🔗 <b>Login Link:</b>\n<code>{login_link}</code>\n\n"
        f"📁 <b>Category:</b> {category}\n"
        f"📝 <b>Remaining:</b> {limit - used - 1}/{limit}\n"
        f"⏰ <b>Auto-delete:</b> {auto_del}s"
    )

    msg = await cb.message.edit_text(
        response,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open Login Page", url=login_link)],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ]),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass


# ════════════════════════════════════════════════════
# CALLBACK: Download account .txt
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"dl_acc_(\d+)"))
async def cb_download_acc(client, cb: CallbackQuery):
    acc_id = int(cb.matches[0].group(1))
    acc = db.get_account(acc_id)
    if not acc:
        await cb.answer("❌ Account not found!", show_alert=True)
        return

    token = db.create_login_token(acc['id'], acc['cookie'])
    login_link = create_login_link(token)

    content = (
        f"╔══════════════════════════════════════╗\n"
        f"║  NETFLIX PREMIUM ACCOUNT              ║\n"
        f"╚══════════════════════════════════════╝\n\n"
        f"📧 Email: {acc['email'] or 'N/A'}\n"
        f"📱 Phone: {acc['phone'] or 'N/A'}\n"
        f"🌍 Country: {acc['country'] or 'N/A'}\n"
        f"📋 Plan: {acc['plan'] or 'Premium'}\n"
        f"📊 Status: {acc['subscription_status'] or 'CURRENT_MEMBER'}\n"
        f"🖥️ Screen: {acc['screen_type'] or 'HD'}\n\n"
        f"🍪 Cookie:\n{acc['cookie']}\n\n"
        f"🔗 Login Link:\n{login_link}\n\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Bot: {BOT_NAME} v{BOT_VERSION}"
    )

    bio = BytesIO(content.encode('utf-8'))
    bio.name = f"netflix_account_{acc_id}.txt"

    auto_del = int(db.get_setting('auto_delete', '300'))
    msg = await cb.message.reply_document(
        document=bio,
        caption=(
            f"📄 <b>Netflix Account #{acc_id}</b>\n"
            f"🔗 {login_link}\n"
            f"⏰ Auto-delete: {auto_del}s"
        ),
        parse_mode=enums.ParseMode.HTML
    )

    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass


# ════════════════════════════════════════════════════
# CALLBACK: Full Cookie display
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"full_ck_(\d+)"))
async def cb_full_cookie(client, cb: CallbackQuery):
    acc_id = int(cb.matches[0].group(1))
    acc = db.get_account(acc_id)
    if not acc:
        await cb.answer("❌ Not found!", show_alert=True)
        return

    auto_del = int(db.get_setting('auto_delete', '300'))
    msg = await cb.message.reply_text(
        f"🍪 <b>Full Cookie:</b>\n\n<code>{acc['cookie']}</code>\n\n⏰ Auto-delete: {auto_del}s",
        parse_mode=enums.ParseMode.HTML
    )

    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass


# ════════════════════════════════════════════════════
# CALLBACK: Send File
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("send_file"))
async def cb_send_file(client, cb: CallbackQuery):
    uid = cb.from_user.id
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return

    db.set_user_state(uid, "waiting_file")
    await cb.message.edit_text(
        "📄 <b>Send File .txt</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Upload a <b>.txt file</b> containing Netflix cookies.\n\n"
        "📝 <b>Formats Supported:</b>\n\n"
        "1️⃣ <b>Simple Cookie:</b>\n"
        "<code>NetflixId=v%3D2%26s%3Dabc123; nfSessionId=xyz789</code>\n\n"
        "2️⃣ <b>With Metadata (pipe-separated):</b>\n"
        "<code>cookie|email|phone|country|plan|status|screen_type</code>\n\n"
        "💡 One cookie per line\n"
        "💡 Maximum 500 cookies per file\n\n"
        "⏳ <i>Waiting for your file...</i>",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# CALLBACK: Send Text
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("send_text"))
async def cb_send_text(client, cb: CallbackQuery):
    uid = cb.from_user.id
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return

    db.set_user_state(uid, "waiting_text")
    await cb.message.edit_text(
        "💬 <b>Send Cookie Text</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Paste your <b>Netflix cookie string</b> directly.\n\n"
        "📝 <b>Format:</b>\n"
        "<code>NetflixId=v%3D2%26s%3Dabc; nfSessionId=xyz</code>\n\n"
        "💡 You can also use pipe-separated format:\n"
        "<code>cookie|email|phone|country|plan|status</code>\n\n"
        "💡 Multiple cookies: one per line\n\n"
        "⏳ <i>Waiting for your message...</i>",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# CALLBACK: Check Cookie
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("check_cookie"))
async def cb_check_cookie(client, cb: CallbackQuery):
    uid = cb.from_user.id
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return

    db.set_user_state(uid, "checking_cookie")
    await cb.message.edit_text(
        "🔍 <b>Cookie Validity Checker</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send a Netflix cookie string to verify if it's still active.\n\n"
        "💡 The bot will check the cookie against Netflix servers\n"
        "💡 Results are instant\n\n"
        "⏳ <i>Waiting for cookie...</i>",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# HANDLE DOCUMENT UPLOADS
# ════════════════════════════════════════════════════

@app.on_message(filters.private & filters.document)
async def handle_document(client, message: Message):
    uid = message.from_user.id
    state, state_data = db.get_user_state(uid)

    if state not in ["waiting_file", "adm_upload"]:
        return

    if db.is_banned(uid) and not is_admin(uid):
        return

    if not message.document.file_name or not message.document.file_name.endswith('.txt'):
        await message.reply_text(
            "❌ Please send a <b>.txt</b> file only!",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # File size check
    max_size = int(db.get_setting('max_file_size', '5242880'))
    if message.document.file_size > max_size:
        await message.reply_text(
            f"❌ File too large! Max size: {max_size // 1024 // 1024}MB",
            parse_mode=enums.ParseMode.HTML
        )
        return

    status_msg = await message.reply_text(
        "⏳ <b>Processing file...</b>\n\n📊 Reading cookies...",
        parse_mode=enums.ParseMode.HTML
    )

    try:
        file_path = await message.download()
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        os.remove(file_path)
    except Exception as e:
        await status_msg.edit_text(f"❌ Error reading file: `{e}`")
        return

    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        await status_msg.edit_text("❌ No cookies found in the file!")
        return

    max_cookies = int(db.get_setting('max_cookies_per_file', '500'))
    if len(lines) > max_cookies:
        lines = lines[:max_cookies]
        await status_msg.edit_text(
            f"⚠️ Too many cookies! Processing first {max_cookies}..."
        )

    added = 0
    failed = 0
    results = []

    for i, line in enumerate(lines, 1):
        try:
            parsed = parse_cookie_line(line)
            cookie = parsed['cookie']

            if not cookie or len(cookie) < 10:
                failed += 1
                continue

            acc_id = db.add_account(
                cookie=cookie,
                email=parsed['email'],
                phone=parsed['phone'],
                country=parsed['country'],
                plan=parsed['plan'],
                status=parsed['status'],
                screen_type=parsed['screen_type'],
                category=parsed['category'],
                added_by=uid,
                source="file_upload"
            )

            token = db.create_login_token(acc_id, cookie)
            login_link = create_login_link(token)
            results.append(f"🔑 Line {i}: {login_link}")
            added += 1
        except Exception as e:
            failed += 1
            logger.error(f"Error processing line {i}: {e}")

    # Send results
    if added == 0:
        await status_msg.edit_text(
            "❌ No valid cookies found in the file!\n\n"
            "Check the format and try again.",
            reply_markup=cancel_kb(),
            parse_mode=enums.ParseMode.HTML
        )
        return

    if len(results) <= 5:
        response = (
            f"✅ <b>File Processed Successfully!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>Results:</b>\n"
            f"   ✅ Added: {added}\n"
            f"   ❌ Failed: {failed}\n\n"
        )
        for r in results:
            response += r + "\n\n"
    else:
        # Send as file
        file_content = "\n\n".join(results)
        bio = BytesIO(file_content.encode('utf-8'))
        bio.name = "login_links.txt"
        await message.reply_document(
            document=bio,
            caption=f"✅ {added} login links generated!\n❌ {failed} failed"
        )
        await status_msg.delete()
        db.clear_user_state(uid)
        db.log_event('file_upload', uid, json.dumps({'added': added, 'failed': failed}))
        return

    response += "\n💡 Click link → Open Login Page → Copy Cookie → Open Netflix! 🚀"

    buttons = []
    for _, link in [(r.split(": ", 1)) for r in results if ": " in r]:
        buttons.append([InlineKeyboardButton("🚀 Open Login", url=link)])
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")])

    auto_del = int(db.get_setting('auto_delete', '300'))
    response += f"\n⏰ Auto-delete: {auto_del}s"

    msg = await status_msg.edit_text(
        response,
        reply_markup=InlineKeyboardMarkup(buttons[:6]),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

    db.clear_user_state(uid)
    db.log_event('file_upload', uid, json.dumps({'added': added, 'failed': failed}))

    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass


# ════════════════════════════════════════════════════
# HANDLE TEXT MESSAGES
# ════════════════════════════════════════════════════

@app.on_message(filters.private & filters.text & ~filters.command([
    "start", "admin", "stats", "help", "ping"
]))
async def handle_text(client, message: Message):
    uid = message.from_user.id
    state, state_data = db.get_user_state(uid)

    # Admin states
    if is_admin(uid) and state.startswith("adm_"):
        await handle_admin_input(client, message, state, state_data)
        return

    # User states
    if state == "waiting_text":
        await process_cookie_text(client, message)
    elif state == "checking_cookie":
        await process_check_cookie(client, message)
    else:
        # Ignore random messages
        pass


async def process_cookie_text(client, message: Message):
    """Process text cookie input"""
    uid = message.from_user.id
    text = message.text.strip()

    if not text or len(text) < 10:
        await message.reply_text("❌ Invalid cookie string! Send a valid Netflix cookie.")
        return

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    results = []

    for i, line in enumerate(lines, 1):
        parsed = parse_cookie_line(line)
        cookie = parsed['cookie']

        if not cookie or len(cookie) < 10:
            continue

        acc_id = db.add_account(
            cookie=cookie,
            email=parsed['email'],
            phone=parsed['phone'],
            country=parsed['country'],
            plan=parsed['plan'],
            status=parsed['status'],
            screen_type=parsed['screen_type'],
            category=parsed['category'],
            added_by=uid,
            source="text_input"
        )

        token = db.create_login_token(acc_id, cookie, uid)
        login_link = create_login_link(token)
        results.append((cookie, login_link, parsed))

    if not results:
        await message.reply_text("❌ No valid cookies found!")
        return

    auto_del = int(db.get_setting('auto_delete', '300'))

    if len(results) == 1:
        cookie, link, parsed = results[0]
        plan_emoji = {'Premium': '👑', 'Standard': '⭐', 'Basic': '📱'}.get(parsed['plan'], '🎬')
        response = (
            f"✅ <b>Cookie Processed!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📧 <b>Email:</b> <code>{parsed['email'] or 'Not Available'}</code>\n"
            f"🌍 <b>Country:</b> {parsed['country'] or 'Unknown'}\n"
            f"📋 <b>Plan:</b> {plan_emoji} {parsed['plan']}\n\n"
            f"🔗 <b>Direct Login Link:</b>\n<code>{link}</code>\n\n"
            f"💡 Click link → Copy Cookie → Open Netflix → You're in! 🚀\n"
            f"⏰ Auto-delete: {auto_del}s"
        )
    else:
        response = (
            f"✅ <b>{len(results)} Cookies Processed!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for i, (_, link, parsed) in enumerate(results, 1):
            email = parsed['email'] or f"Cookie #{i}"
            response += f"🔑 {email}: <code>{link}</code>\n\n"
        response += f"\n💡 Click link → Open Login → Done! 🚀\n⏰ Auto-delete: {auto_del}s"

    buttons = []
    for _, link, _ in results[:5]:
        buttons.append([InlineKeyboardButton("🚀 Open Login", url=link)])
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")])

    msg = await message.reply_text(
        response,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

    db.clear_user_state(uid)
    db.log_event('text_cookie', uid)

    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass


async def process_check_cookie(client, message: Message):
    """Process cookie validity check"""
    uid = message.from_user.id
    cookie = message.text.strip()

    if not cookie or len(cookie) < 10:
        await message.reply_text("❌ Invalid cookie string!")
        return

    status_msg = await message.reply_text(
        "🔍 <b>Checking cookie validity...</b>\n\n"
        "⏳ Connecting to Netflix servers...\n"
        "⏳ Please wait...",
        parse_mode=enums.ParseMode.HTML
    )

    is_valid, reason = await check_netflix_cookie(cookie)

    if is_valid is True:
        response = (
            "✅ <b>Cookie is VALID!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🟢 <b>Status:</b> Active\n"
            f"📝 <b>Details:</b> {reason}\n\n"
            "This Netflix cookie is currently working.\n"
            "You can use it to login! 🚀"
        )
    elif is_valid is False:
        response = (
            "❌ <b>Cookie is INVALID!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔴 <b>Status:</b> Expired/Revoked\n"
            f"📝 <b>Reason:</b> {reason}\n\n"
            "This Netflix cookie is no longer working.\n"
            "Please generate a new one."
        )
    else:
        response = (
            "⚠️ <b>Unable to Verify</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🟡 <b>Status:</b> Unknown\n"
            f"📝 <b>Reason:</b> {reason}\n\n"
            "Could not verify the cookie.\n"
            "Network error or timeout occurred."
        )

    await status_msg.edit_text(
        response,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ]),
        parse_mode=enums.ParseMode.HTML
    )

    db.clear_user_state(uid)
    db.log_event('cookie_check', uid, json.dumps({'valid': is_valid}))


# ════════════════════════════════════════════════════
# INFO PAGES
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("how_use"))
async def cb_how_use(client, cb: CallbackQuery):
    await cb.message.edit_text(
        "📖 <b>How to Use - Complete Guide</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔑 <b>Generate Now:</b>\n"
        "   → Get a working Netflix cookie + login link\n"
        "   → Click link → Copy Cookie → Open Netflix → Done! 🚀\n\n"
        "📄 <b>Send File .txt:</b>\n"
        "   → Upload .txt file with cookies\n"
        "   → Get login links for each cookie\n"
        "   → One cookie per line\n"
        "   → Supports: cookie|email|phone|country|plan|status\n\n"
        "💬 <b>Send Text:</b>\n"
        "   → Paste cookie string directly\n"
        "   → Get instant login link\n\n"
        "🔍 <b>Check Cookie:</b>\n"
        "   → Verify if a cookie is still valid\n"
        "   → Real-time Netflix server check\n\n"
        "📁 <b>Categories:</b>\n"
        "   → Choose specific plan types\n"
        "   → Premium 4K, HD, Standard, etc.\n\n"
        "⚠️ <b>Important:</b>\n"
        "   • Daily limit applies (upgrade for more)\n"
        "   • Messages auto-delete for security\n"
        "   • Must stay in required channels\n"
        "   • Don't share cookies publicly\n"
        "   • For personal use only",
        reply_markup=back_kb(),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex("my_stats"))
async def cb_my_stats(client, cb: CallbackQuery):
    uid = cb.from_user.id
    user = db.get_user(uid)
    if not user:
        await cb.answer("❌ Not found!", show_alert=True)
        return

    limit = db.get_user_daily_limit(uid)
    today = db.get_daily_count(uid)
    pct = int((today / limit) * 100) if limit > 0 else 0
    bar = progress_bar(today, limit)

    vip_text = ""
    if user['vip_level'] > 0:
        vip_text = f"\n👑 <b>VIP Level:</b> {user['vip_level']}"

    ref_text = ""
    if user['referral_code']:
        ref_text = f"\n🔗 <b>Referral Code:</b> <code>{user['referral_code']}</code>"

    await cb.message.edit_text(
        f"📊 <b>Your Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Name:</b> {cb.from_user.first_name}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📅 <b>Joined:</b> {format_time_ago(user['joined_date'])}\n"
        f"{vip_text}{ref_text}\n\n"
        f"📝 <b>Today's Usage:</b>\n"
        f"   {bar} {today}/{limit} ({pct}%)\n\n"
        f"📈 <b>Total Generated:</b> {user['total_generated']}\n"
        f"🔍 <b>Total Checked:</b> {user['total_checked']}\n"
        f"📊 <b>Total Converted:</b> {user['total_converted']}\n"
        f"{'🚫 Status: Banned' if user['is_banned'] else '✅ Status: Active'}",
        reply_markup=back_kb(),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex("about"))
async def cb_about(client, cb: CallbackQuery):
    stats = db.get_stats_summary()

    await cb.message.edit_text(
        f"💎 <b>About {BOT_NAME}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Version:</b> {BOT_VERSION}\n\n"
        f"🔥 <b>Features:</b>\n"
        f"   • 🔑 Unlimited Cookie Generation\n"
        f"   • 🔗 Direct Login Links\n"
        f"   • 📄 File & Text Processing\n"
        f"   • 🔍 Cookie Validity Checker\n"
        f"   • 📁 Category System\n"
        f"   • 👑 VIP Levels\n"
        f"   • 🔗 Referral System\n"
        f"   • 🛡️ Auto-Delete Security\n"
        f"   • 📊 Advanced Statistics\n"
        f"   • 📺 Force Subscription\n"
        f"   • 🔐 Full Admin Panel\n\n"
        f"👥 <b>Users:</b> {format_number(stats['total_users'])}\n"
        f"📦 <b>Accounts:</b> {format_number(stats['available_accounts'])} available\n"
        f"📝 <b>Today:</b> {stats['today_generated']} generated",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📢 Updates", url=f"https://t.me/{UPDATE_CHANNEL}"),
                InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_CHAT}")
            ],
            [
                InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEV_USERNAME}")
            ],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ]),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN PANEL
# ════════════════════════════════════════════════════

@app.on_message(filters.command("admin") & filters.private)
async def cmd_admin(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("🚫 <b>Unauthorized!</b>", parse_mode=enums.ParseMode.HTML)
        return

    stats = db.get_stats_summary()
    status = "🟢 Online" if db.get_setting('bot_status') == '1' else "🔴 Maintenance"

    await message.reply_text(
        f"🔐 <b>Admin Control Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Bot Status:</b> {status}\n"
        f"👥 <b>Users:</b> {format_number(stats['total_users'])}\n"
        f"📦 <b>Accounts:</b> {format_number(stats['available_accounts'])}/{format_number(stats['total_accounts'])}\n"
        f"📝 <b>Today:</b> {stats['today_generated']} generated\n\n"
        f"👇 <b>Select an option:</b>",
        reply_markup=admin_panel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex("adm_back"))
async def cb_adm_back(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    stats = db.get_stats_summary()
    status = "🟢 Online" if db.get_setting('bot_status') == '1' else "🔴 Maintenance"

    await cb.message.edit_text(
        f"🔐 <b>Admin Control Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Bot Status:</b> {status}\n"
        f"👥 <b>Users:</b> {format_number(stats['total_users'])}\n"
        f"📦 <b>Accounts:</b> {format_number(stats['available_accounts'])}/{format_number(stats['total_accounts'])}\n\n"
        f"👇 <b>Select an option:</b>",
        reply_markup=admin_panel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Dashboard Stats
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_stats"))
async def cb_adm_stats(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    stats = db.get_stats_summary()
    cat_stats = db.get_category_stats()
    country_stats = db.get_country_stats()

    acc_total = stats['total_accounts']
    acc_avail = stats['available_accounts']
    acc_used = stats['used_accounts']
    acc_invalid = stats['invalid_accounts']

    acc_bar = percentage_bar(acc_avail, acc_total) if acc_total > 0 else "N/A"

    text = (
        f"📊 <b>Dashboard Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Bot Status:</b> {'🟢 Online' if db.get_setting('bot_status') == '1' else '🔴 Maintenance'}\n\n"
        f"👥 <b>Users:</b>\n"
        f"   Total: {format_number(stats['total_users'])}\n"
        f"   Active (7d): {format_number(stats['active_users'])}\n"
        f"   Banned: {stats['banned_users']}\n\n"
        f"📦 <b>Accounts:</b>\n"
        f"   Total: {acc_total}\n"
        f"   {acc_bar} available\n"
        f"   ✅ Available: {acc_avail}\n"
        f"   🔴 Used: {acc_used}\n"
        f"   ⚠️ Invalid: {acc_invalid}\n\n"
    )

    if cat_stats:
        text += "📁 <b>By Category:</b>\n"
        for cs in cat_stats:
            text += f"   {cs['category']}: {cs['available']} available / {cs['total']} total\n"
        text += "\n"

    if country_stats:
        text += "🌍 <b>Top Countries:</b>\n"
        for cs in country_stats[:5]:
            text += f"   {cs['country']}: {cs['available']} available / {cs['count']} total\n"
        text += "\n"

    text += (
        f"📺 <b>Force Channels:</b> {stats['channels']}\n"
        f"📝 <b>Today Generated:</b> {stats['today_generated']}\n"
        f"📊 <b>Daily Limit:</b> {db.get_setting('daily_limit')}\n"
        f"⏰ <b>Auto Delete:</b> {db.get_setting('auto_delete')}s\n"
        f"🎫 <b>Token Expiry:</b> {db.get_setting('token_expiry_hours')}h"
    )

    await cb.message.edit_text(
        text,
        reply_markup=admin_panel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Add Account
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_add_acc"))
async def cb_adm_add_acc(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    db.set_user_state(cb.from_user.id, "adm_add_acc")
    await cb.message.edit_text(
        "➕ <b>Add Account</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send account details:\n\n"
        "<b>Format:</b>\n"
        "<code>cookie|email|phone|country|plan|status|screen_type|category</code>\n\n"
        "<b>Example:</b>\n"
        "<code>NetflixId=abc|user@email.com|+1234567890|Brazil|Premium|CURRENT_MEMBER|HD|premium_4k</code>\n\n"
        "💡 Only cookie is required\n"
        "💡 Send just the cookie string alone",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Upload File
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_upload"))
async def cb_adm_upload(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    db.set_user_state(cb.from_user.id, "adm_upload")
    await cb.message.edit_text(
        "📁 <b>Bulk Upload Accounts</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send a <b>.txt file</b> with accounts.\n\n"
        "<b>Format (one per line):</b>\n"
        "<code>cookie|email|phone|country|plan|status|screen_type|category</code>\n\n"
        "💡 Or just one cookie per line\n"
        "💡 Max 500 per file",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Account List
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"adm_acc_list_(\d+)_(\w+)"))
async def cb_adm_acc_list(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    page = int(cb.matches[0].group(1))
    status_filter = cb.matches[0].group(2)
    per_page = 5

    accounts = db.get_accounts(limit=per_page, offset=page * per_page, status=status_filter)
    total = db.get_account_count(status_filter)
    total_pages = (total + per_page - 1) // per_page

    if not accounts:
        await cb.message.edit_text(
            "📋 <b>No accounts found!</b>",
            reply_markup=admin_panel_kb(),
            parse_mode=enums.ParseMode.HTML
        )
        return

    filter_names = {'all': 'All', 'available': 'Available', 'used': 'Used', 'invalid': 'Invalid'}
    response = f"📋 <b>Account List</b> - {filter_names.get(status_filter, 'All')} (Page {page + 1}/{total_pages})\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []

    for acc in accounts:
        if acc['is_used']:
            emoji = "🔴"
        elif not acc['is_valid']:
            emoji = "⚠️"
        else:
            emoji = "✅"
        email_display = acc['email'] or acc['cookie'][:20] + "..."
        response += f"{emoji} #{acc['id']} | {email_display} | {acc['country'] or 'N/A'} | {acc['plan']}\n"
        buttons.append([InlineKeyboardButton(
            f"{emoji} #{acc['id']} - {email_display}",
            callback_data=f"adm_acc_{acc['id']}"
        )])

    # Filter buttons
    filters_row = []
    for fkey, fname in filter_names.items():
        if fkey != status_filter:
            filters_row.append(InlineKeyboardButton(fname, callback_data=f"adm_acc_list_0_{fkey}"))
    if filters_row:
        buttons.append(filters_row)

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_acc_list_{page-1}_{status_filter}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"adm_acc_list_{page+1}_{status_filter}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])

    await cb.message.edit_text(
        response,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Account Detail
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"adm_acc_(\d+)"))
async def cb_adm_acc_detail(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    acc_id = int(cb.matches[0].group(1))
    acc = db.get_account(acc_id)
    if not acc:
        await cb.answer("❌ Not found!", show_alert=True)
        return

    if acc['is_used']:
        status = "🔴 Used"
    elif not acc['is_valid']:
        status = "⚠️ Invalid"
    else:
        status = "✅ Available"

    await cb.message.edit_text(
        f"📋 <b>Account #{acc_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📧 <b>Email:</b> <code>{acc['email'] or 'N/A'}</code>\n"
        f"📱 <b>Phone:</b> <code>{acc['phone'] or 'N/A'}</code>\n"
        f"🌍 <b>Country:</b> {acc['country'] or 'N/A'}\n"
        f"📋 <b>Plan:</b> {acc['plan'] or 'N/A'}\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🖥️ <b>Screen:</b> {acc['screen_type'] or 'N/A'}\n"
        f"📁 <b>Category:</b> {acc['category'] or 'N/A'}\n"
        f"📌 <b>Source:</b> {acc['source'] or 'N/A'}\n"
        f"📅 <b>Added:</b> {format_time_ago(acc['added_date'])}\n"
        f"👤 <b>Added by:</b> {acc['added_by'] or 'N/A'}\n"
        f"🔧 <b>Used by:</b> {acc['used_by'] or 'N/A'}\n"
        f"🔍 <b>Checks:</b> {acc['check_count']}\n\n"
        f"🍪 <b>Cookie:</b>\n<code>{acc['cookie'][:200]}{'...' if len(acc['cookie']) > 200 else ''}</code>",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🗑️ Delete", callback_data=f"adm_del_{acc_id}"),
                InlineKeyboardButton("⚠️ Invalidate", callback_data=f"adm_inv_{acc_id}")
            ],
            [
                InlineKeyboardButton("✅ Validate", callback_data=f"adm_val_{acc_id}"),
                InlineKeyboardButton("🔄 Reset Used", callback_data=f"adm_reset_{acc_id}")
            ],
            [InlineKeyboardButton("🔍 Check Validity", callback_data=f"adm_chk_{acc_id}")],
            [InlineKeyboardButton("🔙 Account List", callback_data="adm_acc_list_0_all")]
        ]),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex(r"adm_del_(\d+)"))
async def cb_adm_del(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.delete_account(int(cb.matches[0].group(1)))
    await cb.answer("✅ Deleted!", show_alert=True)
    await cb_adm_back(client, cb)

@app.on_callback_query(filters.regex(r"adm_inv_(\d+)"))
async def cb_adm_inv(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.invalidate_account(int(cb.matches[0].group(1)))
    await cb.answer("⚠️ Marked invalid!", show_alert=True)

@app.on_callback_query(filters.regex(r"adm_val_(\d+)"))
async def cb_adm_val(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.validate_account(int(cb.matches[0].group(1)))
    await cb.answer("✅ Marked valid!", show_alert=True)

@app.on_callback_query(filters.regex(r"adm_reset_(\d+)"))
async def cb_adm_reset(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.reset_account(int(cb.matches[0].group(1)))
    await cb.answer("🔄 Reset to available!", show_alert=True)


@app.on_callback_query(filters.regex(r"adm_chk_(\d+)"))
async def cb_adm_chk(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    acc_id = int(cb.matches[0].group(1))
    acc = db.get_account(acc_id)
    if not acc:
        await cb.answer("❌ Not found!", show_alert=True)
        return

    await cb.answer("🔍 Checking...", show_alert=False)
    is_valid, reason = await check_netflix_cookie(acc['cookie'])

    if is_valid is True:
        db.update_account_check(acc_id, True)
        await cb.answer(f"✅ VALID - {reason}", show_alert=True)
    elif is_valid is False:
        db.update_account_check(acc_id, False)
        await cb.answer(f"❌ INVALID - {reason}", show_alert=True)
    else:
        await cb.answer(f"⚠️ Unknown - {reason}", show_alert=True)


# ════════════════════════════════════════════════════
# ADMIN: Search
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_search"))
async def cb_adm_search(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_search")
    await cb.message.edit_text(
        "🔍 <b>Search Accounts</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send search query (email, phone, country, cookie part, or category):",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Broadcast
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_broadcast"))
async def cb_adm_broadcast(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_broadcast")
    await cb.message.edit_text(
        "📢 <b>Broadcast Message</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total Users: {db.get_user_count()}\n\n"
        "Send the message to broadcast:\n\n"
        "💡 Supports HTML formatting\n"
        "💡 Supports photos (send with caption)\n"
        "💡 /cancel to abort",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Users
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"adm_users_(\d+)"))
async def cb_adm_users(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    page = int(cb.matches[0].group(1))
    per_page = 10
    users = db.get_all_users(limit=per_page, offset=page * per_page)
    total = db.get_user_count()
    total_pages = (total + per_page - 1) // per_page

    if not users:
        await cb.message.edit_text("👥 No users found!", reply_markup=admin_panel_kb())
        return

    text = f"👥 <b>Users</b> (Page {page + 1}/{total_pages})\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []

    for u in users:
        status = "🚫" if u['is_banned'] else ("👑" if u['vip_level'] > 0 else "👤")
        text += f"{status} {u['first_name']} (@{u['username']}) - <code>{u['user_id']}</code> - Gen: {u['total_generated']}\n"
        buttons.append([InlineKeyboardButton(
            f"{status} {u['first_name']} ({u['user_id']})",
            callback_data=f"adm_user_{u['user_id']}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_users_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"adm_users_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])

    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)


@app.on_callback_query(filters.regex(r"adm_user_(\d+)"))
async def cb_adm_user_detail(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.matches[0].group(1))
    user = db.get_user(uid)
    if not user:
        await cb.answer("❌ Not found!", show_alert=True)
        return

    limit = db.get_user_daily_limit(uid)
    today = db.get_daily_count(uid)

    await cb.message.edit_text(
        f"👤 <b>User Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"👤 <b>Name:</b> {user['first_name']}\n"
        f"📛 <b>Username:</b> @{user['username']}\n"
        f"📅 <b>Joined:</b> {format_time_ago(user['joined_date'])}\n"
        f"🕐 <b>Last Active:</b> {format_time_ago(user['last_active'])}\n"
        f"📝 <b>Today:</b> {today}/{limit}\n"
        f"📈 <b>Total Generated:</b> {user['total_generated']}\n"
        f"👑 <b>VIP Level:</b> {user['vip_level']}\n"
        f"🚫 <b>Banned:</b> {'Yes - ' + user['ban_reason'] if user['is_banned'] else 'No'}\n"
        f"🔗 <b>Referral:</b> {user['referral_code']}",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 Ban", callback_data=f"adm_ban_{uid}"),
                InlineKeyboardButton("✅ Unban", callback_data=f"adm_unban_{uid}")
            ],
            [InlineKeyboardButton("🔙 Users", callback_data="adm_users_0")]
        ]),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: Ban/Unban
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_ban$"))
async def cb_adm_ban(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_ban")
    await cb.message.edit_text(
        "🚫 <b>Ban User</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send user ID to ban:\n\n"
        "Format: <code>user_id|reason</code>\n"
        "Example: <code>123456789|Spamming</code>\n\n"
        "💡 Or just send user ID (default reason will be used)",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex("adm_unban$"))
async def cb_adm_unban(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_unban")
    await cb.message.edit_text(
        "✅ <b>Unban User</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send user ID to unban:",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex(r"adm_ban_(\d+)"))
async def cb_adm_ban_user(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.matches[0].group(1))
    db.ban_user(uid, "Admin ban")
    await cb.answer("🚫 User banned!", show_alert=True)

@app.on_callback_query(filters.regex(r"adm_unban_(\d+)"))
async def cb_adm_unban_user(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.matches[0].group(1))
    db.unban_user(uid)
    await cb.answer("✅ User unbanned!", show_alert=True)


# ════════════════════════════════════════════════════
# ADMIN: Channels
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_add_ch"))
async def cb_adm_add_ch(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_add_ch")
    await cb.message.edit_text(
        "📺 <b>Add Force-Sub Channel</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send channel details:\n\n"
        "Format: <code>channel_id|username|title|invite_link</code>\n"
        "Example: <code>-1001234567890|mychannel|My Channel|https://t.me/mychannel</code>\n\n"
        "💡 Or just send channel username (e.g., @mychannel)",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex("adm_channels"))
async def cb_adm_channels(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = db.get_all_channels()
    if not channels:
        await cb.message.edit_text(
            "📺 <b>No channels added!</b>\n\nAdd channels using the 'Add Channel' button.",
            reply_markup=admin_panel_kb(),
            parse_mode=enums.ParseMode.HTML
        )
        return

    text = "📺 <b>Force-Sub Channels</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for ch in channels:
        link = ch['channel_link'] or f"https://t.me/{ch['channel_username']}"
        text += f"📢 {ch['channel_title']} (@{ch['channel_username']}) - <code>{ch['channel_id']}</code>\n"
        buttons.append([InlineKeyboardButton(
            f"❌ Remove {ch['channel_title']}",
            callback_data=f"adm_rem_ch_{ch['channel_id']}"
        )])

    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])

    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)


@app.on_callback_query(filters.regex(r"adm_rem_ch_(-?\d+)"))
async def cb_adm_rem_ch(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.remove_channel(int(cb.matches[0].group(1)))
    await cb.answer("✅ Channel removed!", show_alert=True)
    await cb_adm_channels(client, cb)


# ════════════════════════════════════════════════════
# ADMIN: Settings
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_settings"))
async def cb_adm_settings(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    settings = db.get_all_settings()
    text = "⚙️ <b>Bot Settings</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    buttons = []
    for s in settings:
        val = s['value'][:30] + "..." if len(s['value']) > 30 else s['value']
        desc = s['description'] or s['key']
        text += f"⚙️ <b>{s['key']}</b>: <code>{val}</code>\n   📝 {desc}\n\n"
        buttons.append([InlineKeyboardButton(
            f"✏️ {s['key']}", callback_data=f"adm_set_{s['key']}"
        )])

    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])

    # Paginate if too many settings
    if len(buttons) > 11:
        buttons = buttons[:10]

    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)


@app.on_callback_query(filters.regex(r"adm_set_(.+)"))
async def cb_adm_set_setting(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    key = cb.matches[0].group(1)
    current = db.get_setting(key, '')

    db.set_user_state(cb.from_user.id, "adm_setting", json.dumps({'key': key}))
    await cb.message.edit_text(
        f"✏️ <b>Setting: {key}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 Current value: <code>{current}</code>\n\n"
        f"Send the new value:\n\n"
        f"💡 Send /cancel to keep current value",
        reply_markup=cancel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: HANDLE TEXT INPUTS (Add Account, Broadcast, Settings etc.)
# ════════════════════════════════════════════════════

async def handle_admin_input(client, message: Message, state, state_data):
    """Handle admin text input states"""
    uid = message.from_user.id
    text = message.text.strip()

    # ── ADD ACCOUNT ──
    if state == "adm_add_acc":
        parsed = parse_cookie_line(text)
        if not parsed['cookie']:
            await message.reply_text("❌ Invalid cookie!", reply_markup=admin_panel_kb())
            db.clear_user_state(uid)
            return

        acc_id = db.add_account(
            cookie=parsed['cookie'],
            email=parsed['email'],
            phone=parsed['phone'],
            country=parsed['country'],
            plan=parsed['plan'],
            status=parsed['status'],
            screen_type=parsed['screen_type'],
            category=parsed['category'],
            added_by=uid,
            source="admin_manual"
        )
        await message.reply_text(
            f"✅ <b>Account Added Successfully!</b>\n\n🆔 ID: #{acc_id}\n📧 Email: {parsed['email'] or 'N/A'}",
            reply_markup=admin_panel_kb(),
            parse_mode=enums.ParseMode.HTML
        )
        db.clear_user_state(uid)
        await log_to_channel(f"➕ <b>New Account Added</b>\n\n🆔 #{acc_id}\n👤 By Admin: {uid}")

    # ── SEARCH ACCOUNTS ──
    elif state == "adm_search":
        results = db.search_accounts(text)
        if not results:
            await message.reply_text(
                "❌ No accounts found matching your query!",
                reply_markup=admin_panel_kb()
            )
        else:
            response = f"🔍 <b>Search Results for:</b> <code>{text}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            buttons = []
            for acc in results[:10]:  # Limit to 10 results
                if acc['is_used']:
                    emoji = "🔴"
                elif not acc['is_valid']:
                    emoji = "⚠️"
                else:
                    emoji = "✅"
                email_display = acc['email'] or acc['cookie'][:20] + "..."
                response += f"{emoji} #{acc['id']} | {email_display}\n"
                buttons.append([InlineKeyboardButton(
                    f"{emoji} #{acc['id']} - {email_display}",
                    callback_data=f"adm_acc_{acc['id']}"
                )])
            buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])
            await message.reply_text(response, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        db.clear_user_state(uid)

    # ── BROADCAST ──
    elif state == "adm_broadcast":
        users = db.get_all_users()
        total = len(users)
        success = 0
        failed = 0
        blocked = 0

        status_msg = await message.reply_text(
            f"📢 <b>Broadcasting...</b>\n\n👥 Total: {total}\n✅ Sent: 0\n❌ Failed: 0",
            parse_mode=enums.ParseMode.HTML
        )

        for i, user in enumerate(users):
            if user['is_banned']:
                continue
            try:
                await client.send_message(user['user_id'], text, parse_mode=enums.ParseMode.HTML)
                success += 1
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                try:
                    await client.send_message(user['user_id'], text, parse_mode=enums.ParseMode.HTML)
                    success += 1
                except:
                    failed += 1
            except:
                failed += 1
                blocked += 1

            # Update status every 20 messages
            if (i + 1) % 20 == 0:
                await status_msg.edit_text(
                    f"📢 <b>Broadcasting...</b>\n\n👥 Total: {total}\n✅ Sent: {success}\n❌ Failed: {failed}",
                    parse_mode=enums.ParseMode.HTML
                )
                await asyncio.sleep(0.5)

        await status_msg.edit_text(
            f"✅ <b>Broadcast Complete!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 Total Users: {total}\n"
            f"✅ Successfully Sent: {success}\n"
            f"❌ Failed: {failed}\n"
            f"🚫 Blocked Bots: {blocked}",
            reply_markup=admin_panel_kb(),
            parse_mode=enums.ParseMode.HTML
        )
        db.clear_user_state(uid)

    # ── BAN USER ──
    elif state == "adm_ban":
        parts = text.split('|')
        try:
            target_id = int(parts[0].strip())
            reason = parts[1].strip() if len(parts) > 1 else "Violation of terms"
            db.ban_user(target_id, reason)
            await message.reply_text(
                f"🚫 <b>User Banned!</b>\n\n🆔 ID: <code>{target_id}</code>\n📝 Reason: {reason}",
                reply_markup=admin_panel_kb(),
                parse_mode=enums.ParseMode.HTML
            )
        except ValueError:
            await message.reply_text("❌ Invalid user ID format!", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

    # ── UNBAN USER ──
    elif state == "adm_unban":
        try:
            target_id = int(text.strip())
            db.unban_user(target_id)
            await message.reply_text(
                f"✅ <b>User Unbanned!</b>\n\n🆔 ID: <code>{target_id}</code>",
                reply_markup=admin_panel_kb(),
                parse_mode=enums.ParseMode.HTML
            )
        except ValueError:
            await message.reply_text("❌ Invalid user ID format!", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

    # ── ADD CHANNEL ──
    elif state == "adm_add_ch":
        parts = text.split('|')
        try:
            if len(parts) >= 2:
                ch_id = int(parts[0].strip())
                ch_uname = parts[1].strip().replace('@', '')
                ch_title = parts[2].strip() if len(parts) > 2 else ch_uname
                ch_link = parts[3].strip() if len(parts) > 3 else f"https://t.me/{ch_uname}"
            else:
                # Try to get channel info from username
                ch_uname = parts[0].strip().replace('@', '')
                try:
                    chat = await client.get_chat(ch_uname)
                    ch_id = chat.id
                    ch_title = chat.title or ch_uname
                    ch_link = chat.invite_link or f"https://t.me/{ch_uname}"
                except:
                    await message.reply_text("❌ Could not find channel! Use format: id|username|title|link", reply_markup=admin_panel_kb())
                    db.clear_user_state(uid)
                    return

            if db.add_channel(ch_id, ch_uname, ch_title, ch_link):
                await message.reply_text(
                    f"✅ <b>Channel Added!</b>\n\n📺 {ch_title}\n🆔 <code>{ch_id}</code>\n🔗 @{ch_uname}",
                    reply_markup=admin_panel_kb(),
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                await message.reply_text("⚠️ Channel already exists!", reply_markup=admin_panel_kb())
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

    # ── SETTING UPDATE ──
    elif state == "adm_setting":
        try:
            data = json.loads(state_data)
            key = data.get('key')
            db.set_setting(key, text)
            await message.reply_text(
                f"✅ <b>Setting Updated!</b>\n\n⚙️ <b>Key:</b> {key}\n📝 <b>New Value:</b> <code>{text}</code>",
                reply_markup=admin_panel_kb(),
                parse_mode=enums.ParseMode.HTML
            )
            await log_to_channel(f"⚙️ <b>Setting Changed</b>\n\n🔑 Key: {key}\n📝 Value: {text}\n👤 Admin: {uid}")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)


# ════════════════════════════════════════════════════
# ADMIN: MAINTENANCE TOGGLE
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_maint"))
async def cb_adm_maint(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    current = db.get_setting('bot_status', '1')
    if current == '1':
        db.set_setting('bot_status', '0')
        status = "🔴 Maintenance Mode ON"
    else:
        db.set_setting('bot_status', '1')
        status = "🟢 Online Mode ON"

    await cb.answer(f"Bot status: {status}", show_alert=True)
    await cb_adm_back(client, cb)


# ════════════════════════════════════════════════════
# ADMIN: CLEAN ACCOUNTS
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_clean_used"))
async def cb_adm_clean_used(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    count = db.clean_used_accounts()
    await cb.answer(f"🧹 Cleaned {count} used accounts!", show_alert=True)
    await cb_adm_back(client, cb)


@app.on_callback_query(filters.regex("adm_clean_invalid"))
async def cb_adm_clean_invalid(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    count = db.clean_invalid_accounts()
    await cb.answer(f"🗑️ Cleaned {count} invalid accounts!", show_alert=True)
    await cb_adm_back(client, cb)


@app.on_callback_query(filters.regex("adm_reset_all"))
async def cb_adm_reset_all(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    count = db.reset_all_used()
    await cb.answer(f"🔄 Reset {count} used accounts to available!", show_alert=True)
    await cb_adm_back(client, cb)


# ════════════════════════════════════════════════════
# ADMIN: BULK CHECK ACCOUNTS
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_bulk_check"))
async def cb_adm_bulk_check(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    await cb.answer("🔍 Starting bulk check... This may take a while.", show_alert=False)
    
    accounts = db.get_accounts(limit=50, offset=0, status="available")
    if not accounts:
        await cb.answer("❌ No available accounts to check!", show_alert=True)
        return

    status_msg = await cb.message.reply_text(
        "🔍 <b>Bulk Checking Accounts...</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⏳ Please wait...",
        parse_mode=enums.ParseMode.HTML
    )

    valid = 0
    invalid = 0
    unknown = 0

    for i, acc in enumerate(accounts, 1):
        is_valid, reason = await check_netflix_cookie(acc['cookie'])
        if is_valid is True:
            db.update_account_check(acc['id'], True)
            valid += 1
        elif is_valid is False:
            db.update_account_check(acc['id'], False)
            invalid += 1
        else:
            unknown += 1

        if i % 5 == 0:
            await status_msg.edit_text(
                f"🔍 <b>Bulk Checking...</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 Checked: {i}/{len(accounts)}\n"
                f"✅ Valid: {valid}\n❌ Invalid: {invalid}\n⚠️ Unknown: {unknown}",
                parse_mode=enums.ParseMode.HTML
            )
            await asyncio.sleep(1)

    await status_msg.edit_text(
        f"✅ <b>Bulk Check Complete!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Total Checked: {len(accounts)}\n"
        f"✅ Valid: {valid}\n❌ Invalid: {invalid}\n⚠️ Unknown: {unknown}",
        reply_markup=admin_panel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: EXPORT DATA
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_export"))
async def cb_adm_export(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    buttons = [
        [InlineKeyboardButton("👥 Export Users (CSV)", callback_data="adm_exp_users")],
        [InlineKeyboardButton("📦 Export Available Accounts", callback_data="adm_exp_avail")],
        [InlineKeyboardButton("📦 Export All Accounts", callback_data="adm_exp_all")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")]
    ]
    await cb.message.edit_text(
        "📤 <b>Export Data</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nSelect what to export:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex("adm_exp_users"))
async def cb_adm_exp_users(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    csv_data = db.export_users_csv()
    if not csv_data:
        await cb.answer("❌ No users to export!", show_alert=True)
        return
    bio = BytesIO(csv_data.encode('utf-8'))
    bio.name = f"users_{datetime.now().strftime('%Y%m%d')}.csv"
    await cb.message.reply_document(document=bio, caption=f"👥 Users Export - {db.get_user_count()} users")
    await cb.answer("✅ Exported!")


@app.on_callback_query(filters.regex("adm_exp_avail"))
async def cb_adm_exp_avail(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    txt_data = db.export_accounts_txt(status_filter="available")
    if not txt_data:
        await cb.answer("❌ No available accounts!", show_alert=True)
        return
    bio = BytesIO(txt_data.encode('utf-8'))
    bio.name = f"accounts_available_{datetime.now().strftime('%Y%m%d')}.txt"
    await cb.message.reply_document(document=bio, caption=f"📦 Available Accounts Export")
    await cb.answer("✅ Exported!")


@app.on_callback_query(filters.regex("adm_exp_all"))
async def cb_adm_exp_all(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    txt_data = db.export_accounts_txt()
    if not txt_data:
        await cb.answer("❌ No accounts to export!", show_alert=True)
        return
    bio = BytesIO(txt_data.encode('utf-8'))
    bio.name = f"accounts_all_{datetime.now().strftime('%Y%m%d')}.txt"
    await cb.message.reply_document(document=bio, caption=f"📦 All Accounts Export")
    await cb.answer("✅ Exported!")


# ════════════════════════════════════════════════════
# ADMIN: ANALYTICS
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_analytics"))
async def cb_adm_analytics(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    gen_24h = db.get_event_count('generate', 24)
    check_24h = db.get_event_count('cookie_check', 24)
    upload_24h = db.get_event_count('file_upload', 24)
    new_users_24h = db.get_event_count('new_user', 24)

    gen_7d = db.get_event_count('generate', 168)
    new_users_7d = db.get_event_count('new_user', 168)

    await cb.message.edit_text(
        f"📈 <b>Analytics Dashboard</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Last 24 Hours:</b>\n"
        f"   🔑 Accounts Generated: {gen_24h}\n"
        f"   🔍 Cookies Checked: {check_24h}\n"
        f"   📄 Files Uploaded: {upload_24h}\n"
        f"   👥 New Users: {new_users_24h}\n\n"
        f"📊 <b>Last 7 Days:</b>\n"
        f"   🔑 Accounts Generated: {gen_7d}\n"
        f"   👥 New Users: {new_users_7d}\n\n"
        f"📦 <b>Current Stock:</b> {db.get_account_count('available')} accounts",
        reply_markup=admin_panel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# ADMIN: CATEGORIES & VIP (Basic UI)
# ════════════════════════════════════════════════════

@app.on_callback_query(filters.regex("adm_categories"))
async def cb_adm_categories(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    categories = db.get_categories()
    cat_stats = db.get_category_stats()
    
    text = "📁 <b>Account Categories</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    
    for cat in categories:
        avail = 0
        for cs in cat_stats:
            if cs['category'] == cat['name']:
                avail = cs['available']
        text += f"{cat['emoji']} <b>{cat['name']}</b> - {avail} available\n📝 {cat['description']}\n\n"
        buttons.append([InlineKeyboardButton(
            f"🗑️ Delete {cat['emoji']} {cat['name']}", 
            callback_data=f"adm_delcat_{cat['name']}"
        )])

    db.set_user_state(cb.from_user.id, "adm_add_cat")
    text += "\n💡 Send new category name to add (format: Name|Emoji|Description)"
    
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)


@app.on_callback_query(filters.regex(r"adm_delcat_(.+)"))
async def cb_adm_del_cat(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    cat_name = cb.matches[0].group(1)
    db.delete_category(cat_name)
    await cb.answer(f"🗑️ Category '{cat_name}' deleted!", show_alert=True)
    await cb_adm_categories(client, cb)


@app.on_callback_query(filters.regex("adm_vip"))
async def cb_adm_vip(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "👑 <b>VIP Management</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Feature available in next update.\n\n"
        "💡 Use Settings to enable/disable VIP system.",
        reply_markup=admin_panel_kb(),
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# COMMAND: /ping (Health Check)
# ════════════════════════════════════════════════════

@app.on_message(filters.command("ping") & filters.private)
async def cmd_ping(client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    end = time.time()
    ping_time = round((end - start) * 1000, 2)
    
    stats = db.get_stats_summary()
    await msg.edit_text(
        f"🏓 <b>Pong!</b>\n\n"
        f"⚡ <b>Latency:</b> {ping_time}ms\n"
        f"📦 <b>Stock:</b> {stats['available_accounts']} accounts\n"
        f"👥 <b>Users:</b> {stats['total_users']}\n"
        f"🤖 <b>Version:</b> {BOT_VERSION}",
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# COMMAND: /stats (Quick Stats for Admins)
# ════════════════════════════════════════════════════

@app.on_message(filters.command("stats") & filters.private)
async def cmd_stats(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = db.get_stats_summary()
    await message.reply_text(
        f"📊 <b>Quick Stats</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Users: {stats['total_users']}\n"
        f"📦 Available: {stats['available_accounts']}\n"
        f"🔴 Used: {stats['used_accounts']}\n"
        f"⚠️ Invalid: {stats['invalid_accounts']}\n"
        f"📝 Today Gen: {stats['today_generated']}",
        parse_mode=enums.ParseMode.HTML
    )


# ════════════════════════════════════════════════════
# SCHEDULED TASKS (Cleanup)
# ════════════════════════════════════════════════════

async def scheduled_cleanup():
    """Run periodic cleanup tasks"""
    while True:
        try:
            # Cleanup expired tokens every hour
            cleaned = db.cleanup_expired_tokens()
            if cleaned > 0:
                logger.info(f"🧹 Cleaned {cleaned} expired tokens")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(3600)  # Run every hour


# ════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     🔥 NETFLIX ULTIMATE PREMIUM BOT 🔥                  ║
    ║     Version: 3.0.0 ULTIMATE                             ║
    ║                                                          ║
    ║     🌐 Web Server: Starting...                          ║
    ║     🤖 Telegram Bot: Starting...                        ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Start web server in background thread
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    logger.info(f"✅ Web server started on {WEB_HOST}:{WEB_PORT}")

    # Start cleanup task
    asyncio.create_task(scheduled_cleanup())

    # Start the bot
    async with app:
        me = await app.get_me()
        logger.info(f"✅ Bot started as @{me.username}")
        
        # Send startup notification to admin
        for admin_id in ADMIN_IDS:
            try:
                await app.send_message(
                    admin_id,
                    f"🟢 <b>Bot Started!</b>\n\n"
                    f"🤖 @{me.username}\n"
                    f"📋 Version: {BOT_VERSION}\n"
                    f"📦 Stock: {db.get_account_count('available')} accounts\n"
                    f"👥 Users: {db.get_user_count()}\n\n"
                    f"Use /admin to access control panel",
                    parse_mode=enums.ParseMode.HTML
                )
            except:
                pass
        
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
