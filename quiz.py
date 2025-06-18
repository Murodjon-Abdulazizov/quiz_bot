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

# Logging sozlamasi
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# .env dan token yuklash
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN topilmadi. .env faylini tekshiring.")
    raise RuntimeError("BOT_TOKEN topilmadi.")

# Foydalanuvchilar holati
user_data = {}

# Savollarni o‘qish funksiyasi (random variant va to‘g‘ri javob)
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
            shuffled_options = [opt for _, opt in option_map]
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

# /start komandasi — tugmalar bilan
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("10 ta savol", callback_data='10')],
        [InlineKeyboardButton("20 ta savol", callback_data='20')],
        [InlineKeyboardButton("30 ta savol", callback_data='30')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📋 Nechta savol ishlamoqchisiz?", reply_markup=reply_markup)

# Callback — foydalanuvchi tugmani bosganda
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id
    count = int(query.data)

    if not os.path.exists("questions.txt"):
        logger.error("questions.txt fayli topilmadi.")
        await query.message.reply_text("❌ questions.txt topilmadi.")
        return

    all_questions = parse_txt_to_json("questions.txt")
    if not all_questions:
        await query.message.reply_text("❗ Fayl bo‘sh yoki noto‘g‘ri formatda.")
        return

    selected_questions = random.sample(all_questions, min(count, len(all_questions)))
    user_data[user_id] = {
        "index": 0,
        "correct": 0,
        "questions": selected_questions
    }
    await query.message.reply_text(f"✅ {len(selected_questions)} ta savol boshlangan!")
    await send_poll(chat_id, context, user_id)

# Poll yuborish
async def send_poll(chat_id, context: ContextTypes.DEFAULT_TYPE, user_id):
    try:
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
        else:
            correct = state["correct"]
            total = len(questions)
            percent = int((correct / total) * 100)
            mark = 5 if percent >= 86 else 4 if percent >= 71 else 3 if percent >= 50 else 2

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📊 Test yakunlandi!\n✅ To‘g‘ri javoblar: {correct}/{total}\n📈 Foiz: {percent}%\n📌 Baho: {mark}"
            )
            del user_data[user_id]
    except Exception as e:
        logger.error(f"Poll yuborishda xatolik: {e}")
        await context.bot.send_message(chat_id, "❌ Xatolik yuz berdi. Qaytadan urinib ko‘ring.")

# Poll javobi qabul qilish
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        poll_id = update.poll_answer.poll_id
        user_id = context.bot_data.get(poll_id)
        if user_id is None or user_id not in user_data:
            return

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
    except Exception as e:
        logger.error(f"Poll javobini qayta ishlashda xatolik: {e}")

# Botni ishga tushurish
if __name__ == "__main__":
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(handle_selection))
        app.add_handler(PollAnswerHandler(handle_poll_answer))
        logger.info("Bot ishga tushmoqda...")

        port = int(os.getenv("PORT", 8443))
        webhook_url = os.getenv("WEBHOOK_URL", "https://your-bot-url.com/webhook")  # <- o‘zgartiring

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            url_path="/webhook"
        )
    except Exception as e:
        logger.error(f"Botni ishga tushirishda xatolik: {e}")
        raise
