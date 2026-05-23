import asyncio
import sys
if sys.version_info >= (3, 10):
    asyncio.set_event_loop(asyncio.new_event_loop())

import os
import json
import time
import random
import logging
import threading
from datetime import datetime, timedelta
from io import BytesIO

from aiohttp import web
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import MessageNotModified, FloodWait

from config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS,
    WEB_BASE_URL, WEB_HOST, WEB_PORT, BOT_VERSION, BOT_NAME,
    DEV_USERNAME, SUPPORT_CHAT, UPDATE_CHANNEL, is_admin
)
from database import UltimateDatabase
from utils import (
    progress_bar, parse_cookie_line, check_netflix_cookie,
    format_account_info, format_time_ago, format_number,
    create_login_link, main_menu_kb, admin_panel_kb, cancel_kb, back_kb
)
from web_server import WebServer

# ══════════════════════════════════════
# LOGGING SETUP
# ══════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s │ %(name)-18s │ %(levelname)-8s │ %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("netflix_bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("NetflixBot")

# ══════════════════════════════════════
# INITIALIZE
# ══════════════════════════════════════
db = UltimateDatabase()

app = Client(
    "NetflixUltimateBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_cooldowns = {}

# ══════════════════════════════════════
# WEB SERVER STARTER
# ══════════════════════════════════════
def start_web_server():
    server = WebServer(db)
    web.run_app(server.app, host=WEB_HOST, port=WEB_PORT, print=None, handle_signals=False)

# ══════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════
async def check_force_sub(user_id):
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
        except:
            not_joined.append(ch)
    return len(not_joined) == 0, not_joined

def check_cooldown(user_id, action="generate"):
    key = f"{user_id}_{action}"
    if key in user_cooldowns:
        remaining = user_cooldowns[key] - time.time()
        if remaining > 0:
            return int(remaining)
    return 0

def set_cooldown(user_id, action="generate", seconds=10):
    key = f"{user_id}_{action}"
    user_cooldowns[key] = time.time() + seconds

async def log_to_channel(text):
    log_ch = int(db.get_setting('log_channel', '0'))
    if not log_ch or log_ch == 0:
        return
    try:
        await app.send_message(log_ch, text, parse_mode=enums.ParseMode.HTML)
    except:
        pass

def build_welcome_text(user, fname):
    uid = user['user_id']
    welcome = db.get_setting('welcome_message', '🎬 Welcome to Netflix Premium Bot!')
    avail = db.get_account_count('available')
    total_users = db.get_user_count()
    limit = db.get_user_daily_limit(uid)
    used = db.get_daily_count(uid)
    announcement = db.get_setting('announcements', '')
    ann_text = f"\n📢 <b>Announcement:</b>\n{announcement}\n━━━━━━━━━━━━━━━━━━━━━━\n" if announcement else ""
    vip_text = f"👑 <b>VIP Level:</b> {user['vip_level']}\n" if user['vip_level'] > 0 else ""
    return (
        f"🎬 <b>Welcome to {BOT_NAME}!</b> 🔥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{ann_text}{welcome}\n\n"
        f"👤 <b>User:</b> <a href='tg://user?id={uid}'>{fname}</a>\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"{vip_text}"
        f"📦 <b>Available:</b> {format_number(avail)}\n"
        f"📝 <b>Today:</b> {used}/{limit}\n"
        f"👥 <b>Users:</b> {format_number(total_users)}\n\n"
        f"👇 <b>Choose an option:</b>"
    )

# ══════════════════════════════════════
# COMMAND: /start
# ══════════════════════════════════════
@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client, message: Message):
    uid = message.from_user.id
    uname = message.from_user.username or ""
    fname = message.from_user.first_name or ""
    lname = message.from_user.last_name or ""
    lang = message.from_user.language_code or "en"
    is_prem = 1 if message.from_user.is_premium else 0
    referred_by = 0
    if len(message.command) > 1:
        try:
            referred_by = int(message.command[1])
        except:
            pass
    is_new = db.register_user(uid, uname, fname, lname, lang, is_prem, referred_by)
    user = db.get_user(uid)
    if is_new:
        db.log_event('new_user', uid)
    if db.is_banned(uid):
        reason = user['ban_reason'] or "Not specified"
        await message.reply_text(f"🚫 <b>Banned!</b>\n📝 Reason: <code>{reason}</code>", parse_mode=enums.ParseMode.HTML)
        return
    if db.get_setting('bot_status') != '1' and not is_admin(uid):
        await message.reply_text(db.get_setting('maintenance_message', '🔧 Under maintenance.'), parse_mode=enums.ParseMode.HTML)
        return
    joined, not_joined = await check_force_sub(uid)
    if not joined:
        buttons = []
        for ch in not_joined:
            link = ch['channel_link'] or f"https://t.me/{ch['channel_username']}" if ch['channel_username'] else f"https://t.me/c/{abs(ch['channel_id'])}"
            buttons.append([InlineKeyboardButton(f"📢 {ch['channel_title'] or 'Join Channel'}", url=link)])
        buttons.append([InlineKeyboardButton("✅ I've Joined - Verify", callback_data="verify_join")])
        await message.reply_text("🔒 <b>Verification Required!</b>\n\nJoin all channels first:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        return
    categories = db.get_categories()
    text = build_welcome_text(user, fname)
    await message.reply_text(text, reply_markup=main_menu_kb(categories), parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

# ══════════════════════════════════════
# COMMAND: /admin
# ══════════════════════════════════════
@app.on_message(filters.command("admin") & filters.private)
async def cmd_admin(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("🚫 Unauthorized!", parse_mode=enums.ParseMode.HTML)
        return
    stats = db.get_stats_summary()
    status = "🟢 Online" if db.get_setting('bot_status') == '1' else "🔴 Maintenance"
    await message.reply_text(
        f"🔐 <b>Admin Control Panel</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Status:</b> {status}\n"
        f"👥 <b>Users:</b> {stats['total_users']}\n"
        f"📦 <b>Accounts:</b> {stats['available_accounts']}/{stats['total_accounts']}\n\n"
        f"👇 <b>Select an option:</b>",
        reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML
    )

# ══════════════════════════════════════
# COMMAND: /ping
# ══════════════════════════════════════
@app.on_message(filters.command("ping") & filters.private)
async def cmd_ping(client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 Pong!")
    end = time.time()
    await msg.edit_text(f"🏓 <b>Pong!</b>\n⚡ Latency: {round((end-start)*1000, 2)}ms", parse_mode=enums.ParseMode.HTML)

# ══════════════════════════════════════
# CALLBACK: verify_join
# ══════════════════════════════════════
@app.on_callback_query(filters.regex("verify_join"))
async def cb_verify_join(client, cb: CallbackQuery):
    uid = cb.from_user.id
    joined, not_joined = await check_force_sub(uid)
    if joined:
        user = db.get_user(uid)
        fname = cb.from_user.first_name or ""
        categories = db.get_categories()
        text = build_welcome_text(user, fname)
        await cb.message.edit_text(text, reply_markup=main_menu_kb(categories), parse_mode=enums.ParseMode.HTML)
        await cb.answer("✅ Verified!", show_alert=False)
    else:
        await cb.answer("❌ You haven't joined all channels yet!", show_alert=True)

# ══════════════════════════════════════
# CALLBACK: back_main & cancel
# ══════════════════════════════════════
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
        await cb.message.edit_text(text, reply_markup=main_menu_kb(categories), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass

@app.on_callback_query(filters.regex("cancel_action"))
async def cb_cancel(client, cb: CallbackQuery):
    uid = cb.from_user.id
    db.clear_user_state(uid)
    await cb_back_main(client, cb)
    await cb.answer("❌ Cancelled!")

@app.on_callback_query(filters.regex("noop"))
async def cb_noop(client, cb: CallbackQuery):
    await cb.answer("📄 Page info", show_alert=False)

# ══════════════════════════════════════
# CALLBACK: gen_now (Generate Account)
# ══════════════════════════════════════
@app.on_callback_query(filters.regex("gen_now"))
async def cb_generate(client, cb: CallbackQuery):
    uid = cb.from_user.id
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return
    if db.get_setting('bot_status') != '1':
        await cb.answer("🔧 Maintenance!", show_alert=True)
        return
    joined, _ = await check_force_sub(uid)
    if not joined:
        await cb.answer("❌ Join channels first!", show_alert=True)
        return
    cd = check_cooldown(uid, "generate")
    if cd > 0:
        await cb.answer(f"⏳ Wait {cd}s", show_alert=True)
        return
    limit = db.get_user_daily_limit(uid)
    used = db.get_daily_count(uid)
    if used >= limit:
        await cb.answer(f"⚠️ Daily limit reached! ({used}/{limit})", show_alert=True)
        return
    account = db.get_available_account()
    if not account:
        await cb.answer("❌ No accounts available! Ask admin to add some.", show_alert=True)
        return
    token = db.create_login_token(account['id'], account['cookie'], uid)
    login_link = create_login_link(token)
    db.mark_account_used(account['id'], uid)
    db.update_daily_usage(uid)
    db.log_event('generate', uid)
    cooldown_sec = int(db.get_setting('generate_cooldown', '10'))
    set_cooldown(uid, "generate", cooldown_sec)
    info = format_account_info(account, include_cookie=True, short_cookie=True)
    auto_del = int(db.get_setting('auto_delete', '300'))
    remaining = limit - used - 1
    response = (
        f"{info}\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Direct Login Link:</b>\n<code>{login_link}</code>\n\n"
        f"💡 Click link → Copy Cookie → Open Netflix → Done! 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Remaining:</b> {remaining}/{limit}\n"
        f"⏰ <b>Auto-delete:</b> {auto_del}s"
    )
    msg = await cb.message.edit_text(
        response,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open Login Page", url=login_link)],
            [InlineKeyboardButton("📥 Download .txt", callback_data=f"dl_acc_{account['id']}"),
             InlineKeyboardButton("📋 Full Cookie", callback_data=f"full_ck_{account['id']}")],
            [InlineKeyboardButton("🔄 Generate Another", callback_data="gen_now"),
             InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ]),
        parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
    )
    await log_to_channel(f"📝 <b>Account Generated</b>\n👤 User: {uid}\n🆔 Account: #{account['id']}")
    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass

# ══════════════════════════════════════
# CALLBACK: gen_cat_ (Generate by Category)
# ══════════════════════════════════════
@app.on_callback_query(filters.regex(r"gen_cat_(.+)"))
async def cb_generate_category(client, cb: CallbackQuery):
    uid = cb.from_user.id
    category = cb.matches[0].group(1).replace('_', ' ')
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return
    limit = db.get_user_daily_limit(uid)
    used = db.get_daily_count(uid)
    if used >= limit:
        await cb.answer(f"⚠️ Limit reached! ({used}/{limit})", show_alert=True)
        return
    account = db.get_available_account(category=category)
    if not account:
        await cb.answer(f"❌ No {category} accounts available!", show_alert=True)
        return
    token = db.create_login_token(account['id'], account['cookie'], uid)
    login_link = create_login_link(token)
    db.mark_account_used(account['id'], uid)
    db.update_daily_usage(uid)
    info = format_account_info(account)
    auto_del = int(db.get_setting('auto_delete', '300'))
    response = f"{info}\n\n🔗 <b>Login:</b>\n<code>{login_link}</code>\n📁 Category: {category}\n⏰ Auto-delete: {auto_del}s"
    msg = await cb.message.edit_text(response, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open Login", url=login_link)],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
    ]), parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass

# ══════════════════════════════════════
# CALLBACK: dl_acc_ & full_ck_
# ══════════════════════════════════════
@app.on_callback_query(filters.regex(r"dl_acc_(\d+)"))
async def cb_download_acc(client, cb: CallbackQuery):
    acc_id = int(cb.matches[0].group(1))
    acc = db.get_account(acc_id)
    if not acc:
        await cb.answer("❌ Not found!", show_alert=True)
        return
    token = db.create_login_token(acc['id'], acc['cookie'])
    login_link = create_login_link(token)
    content = (
        f"╔══════════════════════════════════════╗\n"
        f"║  NETFLIX PREMIUM ACCOUNT              ║\n"
        f"╚══════════════════════════════════════╝\n\n"
        f"📧 Email: {acc['email'] or 'N/A'}\n📱 Phone: {acc['phone'] or 'N/A'}\n🌍 Country: {acc['country'] or 'N/A'}\n📋 Plan: {acc['plan'] or 'Premium'}\n\n"
        f"🍪 Cookie:\n{acc['cookie']}\n\n🔗 Login Link:\n{login_link}"
    )
    bio = BytesIO(content.encode('utf-8'))
    bio.name = f"netflix_account_{acc_id}.txt"
    auto_del = int(db.get_setting('auto_delete', '300'))
    msg = await cb.message.reply_document(document=bio, caption=f"📄 Account #{acc_id}\n⏰ Auto-delete: {auto_del}s", parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass

@app.on_callback_query(filters.regex(r"full_ck_(\d+)"))
async def cb_full_cookie(client, cb: CallbackQuery):
    acc_id = int(cb.matches[0].group(1))
    acc = db.get_account(acc_id)
    if not acc:
        await cb.answer("❌ Not found!", show_alert=True)
        return
    auto_del = int(db.get_setting('auto_delete', '300'))
    msg = await cb.message.reply_text(f"🍪 <b>Full Cookie:</b>\n\n<code>{acc['cookie']}</code>\n\n⏰ Auto-delete: {auto_del}s", parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass

# ══════════════════════════════════════
# CALLBACK: send_file, send_text, check_cookie
# ══════════════════════════════════════
@app.on_callback_query(filters.regex("send_file"))
async def cb_send_file(client, cb: CallbackQuery):
    uid = cb.from_user.id
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return
    db.set_user_state(uid, "waiting_file")
    await cb.message.edit_text(
        "📄 <b>Send File .txt</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\nUpload a <b>.txt file</b> with Netflix cookies.\n\n"
        "📝 <b>Formats:</b>\n1️⃣ Simple: <code>NetflixId=abc123; nfSessionId=xyz</code>\n"
        "2️⃣ With metadata: <code>cookie|email|phone|country|plan|status</code>\n\n💡 One per line\n⏳ <i>Waiting for file...</i>",
        reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex("send_text"))
async def cb_send_text(client, cb: CallbackQuery):
    uid = cb.from_user.id
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return
    db.set_user_state(uid, "waiting_text")
    await cb.message.edit_text(
        "💬 <b>Send Cookie Text</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\nPaste your Netflix cookie string.\n\n"
        "📝 <b>Format:</b>\n<code>NetflixId=abc; nfSessionId=xyz</code>\n\n💡 Multiple cookies: one per line\n⏳ <i>Waiting for message...</i>",
        reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex("check_cookie"))
async def cb_check_cookie(client, cb: CallbackQuery):
    uid = cb.from_user.id
    if db.is_banned(uid):
        await cb.answer("🚫 Banned!", show_alert=True)
        return
    db.set_user_state(uid, "checking_cookie")
    await cb.message.edit_text(
        "🔍 <b>Cookie Validity Checker</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\nSend a Netflix cookie to verify.\n⏳ <i>Waiting for cookie...</i>",
        reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML
    )

# ══════════════════════════════════════
# CALLBACK: Info Pages
# ══════════════════════════════════════
@app.on_callback_query(filters.regex("how_use"))
async def cb_how_use(client, cb: CallbackQuery):
    await cb.message.edit_text(
        "📖 <b>How to Use</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n🔑 <b>Generate Now:</b> Get cookie + login link\n📄 <b>Send File:</b> Upload .txt with cookies\n"
        "💬 <b>Send Text:</b> Paste cookie directly\n🔍 <b>Check Cookie:</b> Verify if cookie works\n\n⚠️ Daily limit applies\n⚠️ Messages auto-delete\n⚠️ Stay in required channels",
        reply_markup=back_kb(), parse_mode=enums.ParseMode.HTML
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
    bar = progress_bar(today, limit)
    await cb.message.edit_text(
        f"📊 <b>Your Stats</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n👤 <b>Name:</b> {cb.from_user.first_name}\n🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📅 <b>Joined:</b> {format_time_ago(user['joined_date'])}\n\n📝 <b>Today:</b> {bar} {today}/{limit}\n📈 <b>Total Generated:</b> {user['total_generated']}",
        reply_markup=back_kb(), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex("about"))
async def cb_about(client, cb: CallbackQuery):
    stats = db.get_stats_summary()
    await cb.message.edit_text(
        f"💎 <b>About {BOT_NAME}</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n🤖 <b>Version:</b> {BOT_VERSION}\n👥 <b>Users:</b> {format_number(stats['total_users'])}\n📦 <b>Accounts:</b> {format_number(stats['available_accounts'])} available",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Updates", url=f"https://t.me/{UPDATE_CHANNEL}"), InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_CHAT}")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ]), parse_mode=enums.ParseMode.HTML
    )

# ══════════════════════════════════════
# HANDLE DOCUMENT UPLOADS
# ══════════════════════════════════════
@app.on_message(filters.private & filters.document)
async def handle_document(client, message: Message):
    uid = message.from_user.id
    state, state_data = db.get_user_state(uid)
    if state not in ["waiting_file", "adm_upload"]:
        return
    if db.is_banned(uid) and not is_admin(uid):
        return
    if not message.document.file_name or not message.document.file_name.endswith('.txt'):
        await message.reply_text("❌ Send <b>.txt</b> file only!", parse_mode=enums.ParseMode.HTML)
        return
    status_msg = await message.reply_text("⏳ <b>Processing file...</b>", parse_mode=enums.ParseMode.HTML)
    try:
        file_path = await message.download()
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        os.remove(file_path)
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")
        return
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        await status_msg.edit_text("❌ No cookies found!")
        return
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
            acc_id = db.add_account(cookie=cookie, email=parsed['email'], phone=parsed['phone'],
                                    country=parsed['country'], plan=parsed['plan'], status=parsed['status'],
                                    screen_type=parsed['screen_type'], category=parsed['category'],
                                    added_by=uid, source="file_upload")
            token = db.create_login_token(acc_id, cookie)
            login_link = create_login_link(token)
            results.append(f"🔑 Line {i}: {login_link}")
            added += 1
        except:
            failed += 1
    if added == 0:
        await status_msg.edit_text("❌ No valid cookies found!", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)
        return
    if len(results) <= 5:
        response = f"✅ <b>Processed!</b> Added: {added}, Failed: {failed}\n\n" + "\n\n".join(results)
    else:
        file_content = "\n\n".join(results)
        bio = BytesIO(file_content.encode('utf-8'))
        bio.name = "login_links.txt"
        await message.reply_document(document=bio, caption=f"✅ {added} links generated!\n❌ {failed} failed")
        await status_msg.delete()
        db.clear_user_state(uid)
        return
    response += "\n\n💡 Click link → Open Login → Done! 🚀"
    buttons = [[InlineKeyboardButton("🚀 Open Login", url=link)] for _, link in [(r.split(": ", 1)) for r in results if ": " in r]]
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")])
    msg = await status_msg.edit_text(response, reply_markup=InlineKeyboardMarkup(buttons[:6]), parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    db.clear_user_state(uid)
    auto_del = int(db.get_setting('auto_delete', '300'))
    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass

# ══════════════════════════════════════
# HANDLE TEXT MESSAGES
# ══════════════════════════════════════
@app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "stats", "help", "ping"]))
async def handle_text(client, message: Message):
    uid = message.from_user.id
    state, state_data = db.get_user_state(uid)
    if is_admin(uid) and state.startswith("adm_"):
        await handle_admin_input(client, message, state, state_data)
        return
    if state == "waiting_text":
        await process_cookie_text(client, message)
    elif state == "checking_cookie":
        await process_check_cookie(client, message)

async def process_cookie_text(client, message: Message):
    uid = message.from_user.id
    text = message.text.strip()
    if not text or len(text) < 10:
        await message.reply_text("❌ Invalid cookie!")
        return
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    results = []
    for line in lines:
        parsed = parse_cookie_line(line)
        cookie = parsed['cookie']
        if not cookie or len(cookie) < 10:
            continue
        acc_id = db.add_account(cookie=cookie, email=parsed['email'], phone=parsed['phone'],
                                country=parsed['country'], plan=parsed['plan'], status=parsed['status'],
                                screen_type=parsed['screen_type'], category=parsed['category'],
                                added_by=uid, source="text_input")
        token = db.create_login_token(acc_id, cookie, uid)
        login_link = create_login_link(token)
        results.append((cookie, login_link, parsed))
    if not results:
        await message.reply_text("❌ No valid cookies found!")
        return
    auto_del = int(db.get_setting('auto_delete', '300'))
    if len(results) == 1:
        cookie, link, parsed = results[0]
        response = (
            f"✅ <b>Cookie Processed!</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n📧 <b>Email:</b> <code>{parsed['email'] or 'N/A'}</code>\n🌍 <b>Country:</b> {parsed['country'] or 'Unknown'}\n"
            f"📋 <b>Plan:</b> {parsed['plan']}\n\n🔗 <b>Login Link:</b>\n<code>{link}</code>\n\n💡 Click link → Done! 🚀\n⏰ Auto-delete: {auto_del}s"
        )
    else:
        response = f"✅ <b>{len(results)} Cookies Processed!</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, (_, link, parsed) in enumerate(results, 1):
            email = parsed['email'] or f"Cookie #{i}"
            response += f"🔑 {email}: <code>{link}</code>\n\n"
    buttons = [[InlineKeyboardButton("🚀 Open Login", url=link)] for _, link, _ in results[:5]]
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")])
    msg = await message.reply_text(response, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    db.clear_user_state(uid)
    await asyncio.sleep(auto_del)
    try:
        await msg.delete()
    except:
        pass

async def process_check_cookie(client, message: Message):
    uid = message.from_user.id
    cookie = message.text.strip()
    if not cookie or len(cookie) < 10:
        await message.reply_text("❌ Invalid cookie!")
        return
    status_msg = await message.reply_text("🔍 <b>Checking...</b>\n⏳ Please wait...", parse_mode=enums.ParseMode.HTML)
    is_valid, reason = await check_netflix_cookie(cookie)
    if is_valid is True:
        response = f"✅ <b>VALID!</b>\n🟢 Status: Active\n📝 {reason}"
    elif is_valid is False:
        response = f"❌ <b>INVALID!</b>\n🔴 Status: Expired\n📝 {reason}"
    else:
        response = f"⚠️ <b>Unknown</b>\n🟡 Status: Unverified\n📝 {reason}"
    await status_msg.edit_text(response, reply_markup=back_kb(), parse_mode=enums.ParseMode.HTML)
    db.clear_user_state(uid)

# ══════════════════════════════════════
# ADMIN CALLBACKS
# ══════════════════════════════════════
@app.on_callback_query(filters.regex("adm_back"))
async def cb_adm_back(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    stats = db.get_stats_summary()
    status = "🟢 Online" if db.get_setting('bot_status') == '1' else "🔴 Maintenance"
    await cb.message.edit_text(
        f"🔐 <b>Admin Panel</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n🤖 <b>Status:</b> {status}\n👥 <b>Users:</b> {stats['total_users']}\n📦 <b>Accounts:</b> {stats['available_accounts']}/{stats['total_accounts']}\n\n👇 Select:",
        reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex("adm_stats"))
async def cb_adm_stats(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    stats = db.get_stats_summary()
    await cb.message.edit_text(
        f"📊 <b>Dashboard</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n👥 Users: {stats['total_users']}\n📦 Available: {stats['available_accounts']}\n🔴 Used: {stats['used_accounts']}\n⚠️ Invalid: {stats['invalid_accounts']}\n📝 Today: {stats['today_generated']}",
        reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex("adm_add_acc"))
async def cb_adm_add_acc(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_add_acc")
    await cb.message.edit_text(
        "➕ <b>Add Account</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\nSend account:\n<code>cookie|email|phone|country|plan|status|screen_type|category</code>\n\n💡 Only cookie is required",
        reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex("adm_upload"))
async def cb_adm_upload(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_upload")
    await cb.message.edit_text("📁 <b>Bulk Upload</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\nSend a <b>.txt file</b> with accounts.\nOne per line. Max 500.", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("adm_search"))
async def cb_adm_search(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_search")
    await cb.message.edit_text("🔍 <b>Search</b>\n\nSend search query:", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("adm_broadcast"))
async def cb_adm_broadcast(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_broadcast")
    await cb.message.edit_text(f"📢 <b>Broadcast</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n👥 Total Users: {db.get_user_count()}\n\nSend message:", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("adm_ban$"))
async def cb_adm_ban(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_ban")
    await cb.message.edit_text("🚫 <b>Ban User</b>\n\nSend: <code>user_id|reason</code>", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("adm_unban$"))
async def cb_adm_unban(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_unban")
    await cb.message.edit_text("✅ <b>Unban User</b>\n\nSend user ID:", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("adm_add_ch"))
async def cb_adm_add_ch(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.set_user_state(cb.from_user.id, "adm_add_ch")
    await cb.message.edit_text("📺 <b>Add Channel</b>\n\nSend: <code>channel_id|username|title|invite_link</code>\n\nOr just send @username", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("adm_channels"))
async def cb_adm_channels(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = db.get_all_channels()
    if not channels:
        await cb.message.edit_text("📺 No channels added!", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        return
    text = "📺 <b>Channels</b>\n\n"
    buttons = []
    for ch in channels:
        text += f"📢 {ch['channel_title']} (@{ch['channel_username']}) - <code>{ch['channel_id']}</code>\n"
        buttons.append([InlineKeyboardButton(f"❌ Remove {ch['channel_title']}", callback_data=f"adm_rem_ch_{ch['channel_id']}")])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex(r"adm_rem_ch_(-?\d+)"))
async def cb_adm_rem_ch(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.remove_channel(int(cb.matches[0].group(1)))
    await cb.answer("✅ Removed!", show_alert=True)
    await cb_adm_channels(client, cb)

@app.on_callback_query(filters.regex("adm_maint"))
async def cb_adm_maint(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    current = db.get_setting('bot_status', '1')
    db.set_setting('bot_status', '0' if current == '1' else '1')
    await cb.answer(f"Bot: {'Maintenance' if current == '1' else 'Online'}", show_alert=True)
    await cb_adm_back(client, cb)

@app.on_callback_query(filters.regex("adm_settings"))
async def cb_adm_settings(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    settings = db.get_all_settings()
    text = "⚙️ <b>Settings</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for s in settings[:10]:
        val = s['value'][:25] + "..." if len(s['value']) > 25 else s['value']
        text += f"⚙️ <b>{s['key']}</b>: <code>{val}</code>\n"
        buttons.append([InlineKeyboardButton(f"✏️ {s['key']}", callback_data=f"adm_set_{s['key']}")])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex(r"adm_set_(.+)"))
async def cb_adm_set_setting(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    key = cb.matches[0].group(1)
    current = db.get_setting(key, '')
    db.set_user_state(cb.from_user.id, "adm_setting", json.dumps({'key': key}))
    await cb.message.edit_text(f"✏️ <b>Setting: {key}</b>\n\nCurrent: <code>{current}</code>\n\nSend new value:", reply_markup=cancel_kb(), parse_mode=enums.ParseMode.HTML)

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
    await cb.answer(f"🔄 Reset {count} accounts!", show_alert=True)
    await cb_adm_back(client, cb)

@app.on_callback_query(filters.regex(r"adm_acc_list_(\d+)_(\w+)"))
async def cb_adm_acc_list(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    page = int(cb.matches[0].group(1))
    status_filter = cb.matches[0].group(2)
    per_page = 5
    accounts = db.get_accounts(limit=per_page, offset=page * per_page, status=status_filter)
    total = db.get_account_count(status_filter)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if not accounts:
        await cb.message.edit_text("📋 No accounts found!", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        return
    filter_names = {'all': 'All', 'available': 'Available', 'used': 'Used', 'invalid': 'Invalid'}
    response = f"📋 <b>Accounts</b> - {filter_names.get(status_filter, 'All')} (Page {page+1}/{total_pages})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for acc in accounts:
        emoji = "🔴" if acc['is_used'] else ("⚠️" if not acc['is_valid'] else "✅")
        email_display = acc['email'] or acc['cookie'][:20] + "..."
        response += f"{emoji} #{acc['id']} | {email_display}\n"
        buttons.append([InlineKeyboardButton(f"{emoji} #{acc['id']} - {email_display}", callback_data=f"adm_acc_{acc['id']}")])
    filters_row = [InlineKeyboardButton(fname, callback_data=f"adm_acc_list_0_{fkey}") for fkey, fname in filter_names.items() if fkey != status_filter]
    if filters_row:
        buttons.append(filters_row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_acc_list_{page-1}_{status_filter}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"adm_acc_list_{page+1}_{status_filter}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Admin", callback_data="adm_back")])
    await cb.message.edit_text(response, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex(r"adm_acc_(\d+)"))
async def cb_adm_acc_detail(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    acc_id = int(cb.matches[0].group(1))
    acc = db.get_account(acc_id)
    if not acc:
        await cb.answer("❌ Not found!", show_alert=True)
        return
    status = "🔴 Used" if acc['is_used'] else ("⚠️ Invalid" if not acc['is_valid'] else "✅ Available")
    await cb.message.edit_text(
        f"📋 <b>Account #{acc_id}</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n📧 <b>Email:</b> <code>{acc['email'] or 'N/A'}</code>\n🌍 <b>Country:</b> {acc['country'] or 'N/A'}\n📋 <b>Plan:</b> {acc['plan'] or 'N/A'}\n"
        f"📊 <b>Status:</b> {status}\n📁 <b>Category:</b> {acc['category'] or 'N/A'}\n\n🍪 <b>Cookie:</b>\n<code>{acc['cookie'][:200]}{'...' if len(acc['cookie']) > 200 else ''}</code>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Delete", callback_data=f"adm_del_{acc_id}"), InlineKeyboardButton("⚠️ Invalidate", callback_data=f"adm_inv_{acc_id}")],
            [InlineKeyboardButton("✅ Validate", callback_data=f"adm_val_{acc_id}"), InlineKeyboardButton("🔄 Reset", callback_data=f"adm_reset_{acc_id}")],
            [InlineKeyboardButton("🔙 List", callback_data="adm_acc_list_0_all")]
        ]), parse_mode=enums.ParseMode.HTML
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
    await cb.answer("🔄 Reset!", show_alert=True)

@app.on_callback_query(filters.regex(r"adm_users_(\d+)"))
async def cb_adm_users(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    page = int(cb.matches[0].group(1))
    per_page = 10
    users = db.get_all_users(limit=per_page, offset=page * per_page)
    total = db.get_user_count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    if not users:
        await cb.message.edit_text("👥 No users!", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        return
    text = f"👥 <b>Users</b> (Page {page+1}/{total_pages})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for u in users:
        s = "🚫" if u['is_banned'] else "👤"
        text += f"{s} {u['first_name']} ({u['user_id']}) - Gen: {u['total_generated']}\n"
        buttons.append([InlineKeyboardButton(f"{s} {u['first_name']} ({u['user_id']})", callback_data=f"adm_user_{u['user_id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_users_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"adm_users_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Admin", callback_data="adm_back")])
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
    await cb.message.edit_text(
        f"👤 <b>User</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n🆔 <b>ID:</b> <code>{uid}</code>\n👤 <b>Name:</b> {user['first_name']}\n📅 <b>Joined:</b> {format_time_ago(user['joined_date'])}\n📈 <b>Total Gen:</b> {user['total_generated']}\n🚫 <b>Banned:</b> {'Yes' if user['is_banned'] else 'No'}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Ban", callback_data=f"adm_ban_{uid}"), InlineKeyboardButton("✅ Unban", callback_data=f"adm_unban_{uid}")],
            [InlineKeyboardButton("🔙 Users", callback_data="adm_users_0")]
        ]), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex(r"adm_ban_(\d+)"))
async def cb_adm_ban_user(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.ban_user(int(cb.matches[0].group(1)), "Admin ban")
    await cb.answer("🚫 Banned!", show_alert=True)

@app.on_callback_query(filters.regex(r"adm_unban_(\d+)"))
async def cb_adm_unban_user(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.unban_user(int(cb.matches[0].group(1)))
    await cb.answer("✅ Unbanned!", show_alert=True)

@app.on_callback_query(filters.regex("adm_export"))
async def cb_adm_export(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📤 <b>Export</b>", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Export Users", callback_data="adm_exp_users")],
        [InlineKeyboardButton("📦 Export Available", callback_data="adm_exp_avail")],
        [InlineKeyboardButton("📦 Export All", callback_data="adm_exp_all")],
        [InlineKeyboardButton("🔙 Admin", callback_data="adm_back")]
    ]), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("adm_exp_users"))
async def cb_adm_exp_users(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    csv_data = db.export_users_csv()
    if not csv_data:
        await cb.answer("❌ No users!", show_alert=True)
        return
    bio = BytesIO(csv_data.encode('utf-8'))
    bio.name = f"users_{datetime.now().strftime('%Y%m%d')}.csv"
    await cb.message.reply_document(document=bio, caption=f"👥 {db.get_user_count()} users")

@app.on_callback_query(filters.regex("adm_exp_avail"))
async def cb_adm_exp_avail(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    txt_data = db.export_accounts_txt(status_filter="available")
    if not txt_data:
        await cb.answer("❌ No accounts!", show_alert=True)
        return
    bio = BytesIO(txt_data.encode('utf-8'))
    bio.name = f"accounts_available_{datetime.now().strftime('%Y%m%d')}.txt"
    await cb.message.reply_document(document=bio, caption="📦 Available accounts")

@app.on_callback_query(filters.regex("adm_exp_all"))
async def cb_adm_exp_all(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    txt_data = db.export_accounts_txt()
    if not txt_data:
        await cb.answer("❌ No accounts!", show_alert=True)
        return
    bio = BytesIO(txt_data.encode('utf-8'))
    bio.name = f"accounts_all_{datetime.now().strftime('%Y%m%d')}.txt"
    await cb.message.reply_document(document=bio, caption="📦 All accounts")

@app.on_callback_query(filters.regex("adm_analytics"))
async def cb_adm_analytics(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    gen_24h = db.get_event_count('generate', 24)
    check_24h = db.get_event_count('cookie_check', 24)
    new_24h = db.get_event_count('new_user', 24)
    await cb.message.edit_text(
        f"📈 <b>Analytics</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n📊 <b>Last 24h:</b>\n   🔑 Generated: {gen_24h}\n   🔍 Checked: {check_24h}\n   👥 New Users: {new_24h}\n📦 <b>Stock:</b> {db.get_account_count('available')} accounts",
        reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex("adm_categories"))
async def cb_adm_categories(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    categories = db.get_categories()
    text = "📁 <b>Categories</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for cat in categories:
        text += f"{cat['emoji']} {cat['name']}\n"
        buttons.append([InlineKeyboardButton(f"🗑️ Delete {cat['name']}", callback_data=f"adm_delcat_{cat['name']}")])
    buttons.append([InlineKeyboardButton("🔙 Admin", callback_data="adm_back")])
    db.set_user_state(cb.from_user.id, "adm_add_cat")
    text += "\n💡 Send new category: Name|Emoji|Description"
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex(r"adm_delcat_(.+)"))
async def cb_adm_del_cat(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db.delete_category(cb.matches[0].group(1))
    await cb.answer("🗑️ Deleted!", show_alert=True)
    await cb_adm_categories(client, cb)

@app.on_callback_query(filters.regex("adm_vip"))
async def cb_adm_vip(client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👑 <b>VIP Management</b>\n\nComing soon!", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)

# ══════════════════════════════════════
# ADMIN TEXT INPUT HANDLER
# ══════════════════════════════════════
async def handle_admin_input(client, message: Message, state, state_data):
    uid = message.from_user.id
    text = message.text.strip()

    if state == "adm_add_acc":
        parsed = parse_cookie_line(text)
        if not parsed['cookie']:
            await message.reply_text("❌ Invalid cookie!", reply_markup=admin_panel_kb())
            db.clear_user_state(uid)
            return
        acc_id = db.add_account(cookie=parsed['cookie'], email=parsed['email'], phone=parsed['phone'],
                                country=parsed['country'], plan=parsed['plan'], status=parsed['status'],
                                screen_type=parsed['screen_type'], category=parsed['category'],
                                added_by=uid, source="admin_manual")
        await message.reply_text(f"✅ <b>Account Added!</b>\n🆔 ID: #{acc_id}", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        db.clear_user_state(uid)

    elif state == "adm_search":
        results = db.search_accounts(text)
        if not results:
            await message.reply_text("❌ No accounts found!", reply_markup=admin_panel_kb())
        else:
            response = f"🔍 <b>Results for:</b> <code>{text}</code>\n\n"
            buttons = []
            for acc in results[:10]:
                emoji = "🔴" if acc['is_used'] else ("⚠️" if not acc['is_valid'] else "✅")
                email_display = acc['email'] or acc['cookie'][:20] + "..."
                response += f"{emoji} #{acc['id']} | {email_display}\n"
                buttons.append([InlineKeyboardButton(f"{emoji} #{acc['id']}", callback_data=f"adm_acc_{acc['id']}")])
            buttons.append([InlineKeyboardButton("🔙 Admin", callback_data="adm_back")])
            await message.reply_text(response, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        db.clear_user_state(uid)

    elif state == "adm_broadcast":
        users = db.get_all_users()
        total = len(users)
        success = 0
        failed = 0
        status_msg = await message.reply_text(f"📢 Broadcasting...\n👥 Total: {total}\n✅ Sent: 0", parse_mode=enums.ParseMode.HTML)
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
            if (i + 1) % 20 == 0:
                await status_msg.edit_text(f"📢 Broadcasting...\n👥 Total: {total}\n✅ Sent: {success}\n❌ Failed: {failed}", parse_mode=enums.ParseMode.HTML)
                await asyncio.sleep(0.5)
        await status_msg.edit_text(f"✅ <b>Broadcast Complete!</b>\n\n✅ Sent: {success}\n❌ Failed: {failed}", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        db.clear_user_state(uid)

    elif state == "adm_ban":
        parts = text.split('|')
        try:
            target_id = int(parts[0].strip())
            reason = parts[1].strip() if len(parts) > 1 else "Violation"
            db.ban_user(target_id, reason)
            await message.reply_text(f"🚫 <b>Banned!</b> ID: <code>{target_id}</code>", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        except:
            await message.reply_text("❌ Invalid format!", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

    elif state == "adm_unban":
        try:
            target_id = int(text.strip())
            db.unban_user(target_id)
            await message.reply_text(f"✅ <b>Unbanned!</b> ID: <code>{target_id}</code>", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        except:
            await message.reply_text("❌ Invalid ID!", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

    elif state == "adm_add_ch":
        parts = text.split('|')
        try:
            if len(parts) >= 2:
                ch_id = int(parts[0].strip())
                ch_uname = parts[1].strip().replace('@', '')
                ch_title = parts[2].strip() if len(parts) > 2 else ch_uname
                ch_link = parts[3].strip() if len(parts) > 3 else f"https://t.me/{ch_uname}"
            else:
                ch_uname = parts[0].strip().replace('@', '')
                try:
                    chat = await client.get_chat(ch_uname)
                    ch_id = chat.id
                    ch_title = chat.title or ch_uname
                    ch_link = chat.invite_link or f"https://t.me/{ch_uname}"
                except:
                    await message.reply_text("❌ Channel not found! Use: id|username|title|link", reply_markup=admin_panel_kb())
                    db.clear_user_state(uid)
                    return
            if db.add_channel(ch_id, ch_uname, ch_title, ch_link):
                await message.reply_text(f"✅ <b>Channel Added!</b>\n📺 {ch_title}", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
            else:
                await message.reply_text("⚠️ Already exists!", reply_markup=admin_panel_kb())
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

    elif state == "adm_setting":
        try:
            data = json.loads(state_data)
            key = data.get('key')
            db.set_setting(key, text)
            await message.reply_text(f"✅ <b>Updated!</b>\n⚙️ {key}: <code>{text}</code>", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

    elif state == "adm_add_cat":
        parts = text.split('|')
        name = parts[0].strip()
        emoji = parts[1].strip() if len(parts) > 1 else "📁"
        desc = parts[2].strip() if len(parts) > 2 else ""
        if db.add_category(name, emoji, desc):
            await message.reply_text(f"✅ <b>Category Added!</b>\n{emoji} {name}", reply_markup=admin_panel_kb(), parse_mode=enums.ParseMode.HTML)
        else:
            await message.reply_text("⚠️ Already exists!", reply_markup=admin_panel_kb())
        db.clear_user_state(uid)

# ══════════════════════════════════════
# SCHEDULED CLEANUP
# ══════════════════════════════════════
async def scheduled_cleanup():
    while True:
        try:
            db.cleanup_expired_tokens()
        except:
            pass
        await asyncio.sleep(3600)

# ══════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════
async def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     🔥 NETFLIX ULTIMATE PREMIUM BOT 🔥                  ║
    ║     Version: 3.0.0 ULTIMATE                             ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    logger.info(f"✅ Web server started on {WEB_HOST}:{WEB_PORT}")
    asyncio.create_task(scheduled_cleanup())
    async with app:
        me = await app.get_me()
        logger.info(f"✅ Bot started as @{me.username}")
        for admin_id in ADMIN_IDS:
            try:
                await app.send_message(
                    admin_id,
                    f"🟢 <b>Bot Started!</b>\n\n🤖 @{me.username}\n📋 Version: {BOT_VERSION}\n📦 Stock: {db.get_account_count('available')} accounts\n👥 Users: {db.get_user_count()}\n\nUse /admin to access control panel",
                    parse_mode=enums.ParseMode.HTML
                )
            except:
                pass
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
