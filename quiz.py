import os
import logging
import asyncio
import random
import json
from dotenv import load_dotenv
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    PollAnswerHandler, CallbackQueryHandler
)

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === Env sozlash ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-bot-url.com/webhook")
PORT = int(os.getenv("PORT", 8443))
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi.")

# === Foydalanuvchi ruxsatlarini boshqarish ===
ALLOWED_FILE = "allowed_users.json"

def load_allowed_users():
    try:
        with open(ALLOWED_FILE, 'r') as f:
            return set(json.load(f))
    except:
        return set()

def save_allowed_users(users):
    with open(ALLOWED_FILE, 'w') as f:
        json.dump(list(users), f)

def add_allowed_user(user_id):
    users = load_allowed_users()
    users.add(user_id)
    save_allowed_users(users)

def remove_allowed_user(user_id):
    users = load_allowed_users()
    users.discard(user_id)
    save_allowed_users(users)

user_data = {}
poll_timeout_tasks = {}

# === Savollarni yuklash ===
def parse_txt_to_json(txt_path):
    questions = []
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        i = 0
        while i < len(lines):
            if i + 5 >= len(lines):
                break
            question = lines[i]
            options_raw = [lines[i+1][3:], lines[i+2][3:], lines[i+3][3:], lines[i+4][3:]]
            correct_line = lines[i+5].split(":")
            if len(correct_line) < 2:
                break
            correct_letter = correct_line[1].strip().upper()
            if correct_letter not in {'A', 'B', 'C', 'D'}:
                break
            correct_index_before_shuffle = {'A': 0, 'B': 1, 'C': 2, 'D': 3}[correct_letter]
            option_map = list(enumerate(options_raw))
            random.shuffle(option_map)
            shuffled_options = [opt[:100] for _, opt in option_map]
            new_correct_index = next(i for i, (orig_idx, _) in enumerate(option_map) if orig_idx == correct_index_before_shuffle)
            questions.append({
                "question": question,
                "options": shuffled_options,
                "correct_option_id": new_correct_index
            })
            i += 6
    except Exception as e:
        logger.error(f"Xatolik: {e}")
    return questions

# === /start komandasi ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    allowed_users = load_allowed_users()

    if user_id not in allowed_users:
        keyboard = [
            [
                InlineKeyboardButton("✅ Ruxsat berish", callback_data=f"allow_{user_id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"deny_{user_id}")
            ]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        text = f"🆕 Yangi foydalanuvchi:\n👤 {user.full_name}\n🆔 `{user_id}`"
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=markup, parse_mode="Markdown")
        await update.message.reply_text("⏳ Ruxsat so‘rovi yuborildi. Iltimos, kuting.")
        return

    await show_main_menu(update.effective_chat.id, context)

# === Ruxsat bergandan so‘ng: Testni boshlash tugmasi ===
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        await query.message.reply_text("⛔ Siz bu amalni bajara olmaysiz.")
        return

    data = query.data
    if data.startswith("allow_"):
        user_id = int(data.split("_")[1])
        add_allowed_user(user_id)
        await query.edit_message_text(f"✅ {user_id} ga ruxsat berildi.")

        keyboard = [[InlineKeyboardButton("🟢 Testni boshlash", callback_data='show_menu')]]
        markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Sizga botdan foydalanishga ruxsat berildi!",
            reply_markup=markup
        )

    elif data.startswith("deny_"):
        user_id = int(data.split("_")[1])
        await query.edit_message_text(f"❌ {user_id} rad etildi.")
        await context.bot.send_message(chat_id=user_id, text="❌ Sizga ruxsat berilmadi.")

# === /users komandasi ===
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Sizga ruxsat yo‘q.")
        return

    users = load_allowed_users()
    if not users:
        await update.message.reply_text("📭 Hozircha hech kimga ruxsat berilmagan.")
        return

    msg = "📋 Ruxsat berilgan foydalanuvchilar:\n"
    for uid in sorted(users):
        msg += f"- `{uid}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# === show_main_menu ===
async def show_main_menu(chat_id, context):
    keyboard = [
        [InlineKeyboardButton("🩺 Hamshiralik ishi", callback_data='nursing')],
        [InlineKeyboardButton("💻 AKT", callback_data='akt')],
        [InlineKeyboardButton("📚 To‘g‘rilangan javoblar", callback_data='corrected')]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id, "Fanni tanlang:", reply_markup=markup)

# === Botni ishga tushirish ===
if __name__ == "__main__":
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("users", list_users))
        app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^(allow_|deny_)"))
        logger.info("Bot ishga tushmoqda...")

        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            url_path="/webhook"
        )
    except Exception as e:
        logger.error(f"Botni ishga tushirishda xatolik: {e}")
        raise