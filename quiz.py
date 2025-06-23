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

    # Ruxsat berilgan foydalanuvchiga menyu ko‘rsatish
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

        # Testni boshlash tugmasi bilan yuborish
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

# === Testni boshlash va fan menyusini ko‘rsatish ===
async def show_main_menu(chat_id, context):
    keyboard = [
        [InlineKeyboardButton("🩺 Hamshiralik ishi", callback_data='nursing')],
        [InlineKeyboardButton("💻 AKT", callback_data='akt')],
        [InlineKeyboardButton("📚 To‘g‘rilangan javoblar", callback_data='corrected')]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id, "Fanni tanlang:", reply_markup=markup)

# === /kick komandasi ===
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Siz bu buyruqni bajara olmaysiz.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❗ Foydalanuvchi ID si kerak: /kick <id>")
        return
    try:
        user_id = int(context.args[0])
        remove_allowed_user(user_id)
        await update.message.reply_text(f"🚫 {user_id} botdan chiqarildi.")
        await context.bot.send_message(chat_id=user_id, text="🚫 Sizning ruxsatingiz olib tashlandi.")
    except:
        await update.message.reply_text("❌ Xatolik yuz berdi.")

# === Fanni tanlash yoki tugmalarni boshqarish ===
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id
    data = query.data

    allowed_users = load_allowed_users()
    if int(user_id) not in allowed_users:
        await query.message.reply_text("⛔ Sizga ruxsat berilmagan.")
        return

    if data == 'restart' or data == 'show_menu':
        await show_main_menu(chat_id, context)
        return

    if data == 'nursing':
        keyboard = [
            [InlineKeyboardButton("30 ta savol", callback_data='nursing_30')],
            [InlineKeyboardButton("40 ta savol", callback_data='nursing_40')],
            [InlineKeyboardButton("50 ta savol", callback_data='nursing_50')]
        ]
        await query.message.reply_text("📋 Savollar sonini tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'akt':
        all_questions = parse_txt_to_json("questions_akt.txt")
        if not all_questions:
            await query.message.reply_text("❗ AKT savollari topilmadi.")
            return
        selected = random.sample(all_questions, min(20, len(all_questions)))
        user_data[user_id] = {"index": 0, "correct": 0, "questions": selected}
        await query.message.reply_text("✅ AKT fanidan 20 ta test boshlandi!")
        await send_poll(chat_id, context, user_id)
        return

    if data == 'corrected':
        all_questions = parse_txt_to_json("questions_corrected.txt")
        if not all_questions:
            await query.message.reply_text("❗ To‘g‘rilangan javoblar topilmadi.")
            return
        selected = all_questions[:20]
        user_data[user_id] = {"index": 0, "correct": 0, "questions": selected}
        await query.message.reply_text("✅ To‘g‘rilangan javoblardan 20 ta test boshlandi!")
        await send_poll(chat_id, context, user_id)
        return

    if data.startswith("nursing_"):
        count = int(data.split("_")[1])
        all_questions = parse_txt_to_json("questions_nursing.txt")
        if not all_questions:
            await query.message.reply_text("❗ Hamshiralik savollari topilmadi.")
            return
        selected = random.sample(all_questions, min(count, len(all_questions)))
        user_data[user_id] = {"index": 0, "correct": 0, "questions": selected}
        await query.message.reply_text(f"✅ {count} ta test boshlandi!")
        await send_poll(chat_id, context, user_id)

# === Poll yuborish ===
async def send_poll(chat_id, context, user_id):
    state = user_data[user_id]
    index = state["index"]
    questions = state["questions"]

    if index < len(questions):
        q = questions[index]
        poll_msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=q["question"],
            options=q["options"],
            type=Poll.QUIZ,
            correct_option_id=q["correct_option_id"],
            is_anonymous=False
        )
        context.bot_data[poll_msg.poll.id] = user_id
        task = asyncio.create_task(timeout_next_poll(chat_id, context, user_id, poll_msg.poll.id))
        poll_timeout_tasks[poll_msg.poll.id] = task
    else:
        correct = state["correct"]
        total = len(questions)
        percent = int((correct / total) * 100)
        mark = 5 if percent >= 86 else 4 if percent >= 71 else 3 if percent >= 50 else 2
        keyboard = [[InlineKeyboardButton("🔁 Yana test ishlash", callback_data='restart')]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📊 Test yakunlandi!\n✅ To‘g‘ri javoblar: {correct}/{total}\n📈 Foiz: {percent}%\n📌 Baho: {mark}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        del user_data[user_id]

# === Avtomatik o'tish ===
async def timeout_next_poll(chat_id, context, user_id, poll_id):
    await asyncio.sleep(45)
    if user_id in user_data:
        state = user_data[user_id]
        index = state["index"]
        questions = state["questions"]
        if index < len(questions):
            await context.bot.send_message(chat_id, f"⏱ 45 soniya o'tdi.\n❌ \"{questions[index]['question']}\" savoliga javob berilmadi.")
            state["index"] += 1
            await asyncio.sleep(1)
            await send_poll(chat_id, context, user_id)

# === Poll javobi ===
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    user_id = context.bot_data.get(poll_id)
    if user_id is None or user_id not in user_data:
        return
    task = poll_timeout_tasks.pop(poll_id, None)
    if task:
        task.cancel()
    state = user_data[user_id]
    index = state["index"]
    questions = state["questions"]
    if index < len(questions):
        correct_id = questions[index]["correct_option_id"]
        if update.poll_answer.option_ids and update.poll_answer.option_ids[0] == correct_id:
            state["correct"] += 1
        state["index"] += 1
        await asyncio.sleep(1.5)
        chat_id = update.poll_answer.user.id
        await send_poll(chat_id, context, user_id)

# === Botni ishga tushirish ===
if __name__ == "__main__":
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("kick", kick))
        app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^(allow_|deny_)"))
        app.add_handler(CallbackQueryHandler(handle_selection))
        app.add_handler(PollAnswerHandler(handle_poll_answer))
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
