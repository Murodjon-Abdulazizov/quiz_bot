import os
import logging
import asyncio
import random
from dotenv import load_dotenv
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    PollAnswerHandler, CallbackQueryHandler
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Token
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi.")

user_data = {}
poll_timeout_tasks = {}

# 1. Savollarni yuklash
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

# 2. /start — 30/40/50 tanlovini ko‘rsatish
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_test_options(update.effective_chat.id, context)

# 3. Tugma bosilganda
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id
    data = query.data

    if data == 'restart':
        await show_test_options(chat_id, context)
        return

    count = int(data)
    all_questions = parse_txt_to_json("questions_nursing.txt") 
    parse_txt_to_json("questions_akt.txt") 

    if not all_questions:
        await query.message.reply_text("❗ Fayl bo‘sh yoki noto‘g‘ri formatda.")
        return

    selected_questions = random.sample(all_questions, min(count, len(all_questions)))
    user_data[user_id] = {
        "index": 0,
        "correct": 0,
        "questions": selected_questions
    }
    await query.message.reply_text(f"✅ {len(selected_questions)} ta savol boshlangan! Har bir savol uchun 45 soniya vaqt bor.")
    await send_poll(chat_id, context, user_id)

# 4. Tanlash tugmalari — 30/40/50
async def show_test_options(chat_id, context):
    keyboard = [
        [InlineKeyboardButton("30 ta savol", callback_data='30')],
        [InlineKeyboardButton("40 ta savol", callback_data='40')],
        [InlineKeyboardButton("50 ta savol", callback_data='50')]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id, "📋 Nechta savol ishlamoqchisiz?", reply_markup=markup)

# 5. Poll yuborish
async def send_poll(chat_id, context: ContextTypes.DEFAULT_TYPE, user_id):
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
        markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📊 Test yakunlandi!\n✅ To‘g‘ri javoblar: {correct}/{total}\n📈 Foiz: {percent}%\n📌 Baho: {mark}",
            reply_markup=markup
        )
        del user_data[user_id]

# 6. 45 soniya ichida javob bo‘lmasa
async def timeout_next_poll(chat_id, context, user_id, poll_id):
    await asyncio.sleep(45)
    if user_id in user_data:
        state = user_data[user_id]
        index = state["index"]
        questions = state["questions"]
        if index < len(questions):
            question_text = questions[index]["question"]
            await context.bot.send_message(chat_id, f"⏱ 45 soniya o'tdi.\n❌ \"{question_text}\" savoliga javob berilmadi.")
            state["index"] += 1
            await asyncio.sleep(1)
            await send_poll(chat_id, context, user_id)

# 7. Pollga javob kelsa
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
        await asyncio.sleep(1.0)
        chat_id = update.poll_answer.user.id
        await send_poll(chat_id, context, user_id)

# 8. Botni ishga tushurish
if __name__ == "__main__":
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(handle_selection))
        app.add_handler(PollAnswerHandler(handle_poll_answer))
        logger.info("Bot ishga tushmoqda...")

        port = int(os.getenv("PORT", 8443))
        webhook_url = os.getenv("WEBHOOK_URL", "https://your-bot-url.com/webhook")  # ← O'zingizning webhook URL’ingiz

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            url_path="/webhook"
        )
    except Exception as e:
        logger.error(f"Botni ishga tushirishda xatolik: {e}")
        raise
