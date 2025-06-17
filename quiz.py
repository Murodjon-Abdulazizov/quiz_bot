import os
import random
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Savollar va javoblar bazasi (masalan)
questions = {
    1: {
        "question": "2 + 2 = ?",
        "answers": ["2", "3", "4", "5"],
        "correct": "4"
    },
    2: {
        "question": "Python'da ro‘yxatni aralashtirish uchun qaysi funksiya ishlatiladi?",
        "answers": ["sort()", "shuffle()", "randomize()", "mix()"],
        "correct": "shuffle()"
    }
}

# Bot tokeni va webhook URL
TOKEN = os.getenv("BOT_TOKEN")
URL = os.getenv("RENDER_EXTERNAL_URL")

def create_quiz_keyboard(question_id):
    answers = questions[question_id]["answers"].copy()  # Asl ro‘yxatni o‘zgartirmaslik uchun nusxa
    random.shuffle(answers)  # Javoblar tartibini tasodifiy qilish
    keyboard = [
        [InlineKeyboardButton(answer, callback_data=answer) for answer in answers[i:i+2]]
        for i in range(0, len(answers), 2)  # Har bir qatorda 2 ta tugma
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Bot ishga tushmoqda...")
    await update.message.reply_text("Quiz botiga xush kelibsiz! /quiz buyrug‘i bilan boshlang.")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question_id = 1  # Birinchi savol
    question = questions[question_id]["question"]
    keyboard = create_quiz_keyboard(question_id)
    await update.message.reply_text(question, reply_markup=keyboard)
    context.user_data["current_question"] = question_id

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_answer = query.data
    question_id = context.user_data.get("current_question")
    correct_answer = questions[question_id]["correct"]

    if user_answer == correct_answer:
        await query.message.reply_text("To‘g‘ri javob! 🎉 Keyingi savol uchun /quiz buyrug‘ini bosing.")
    else:
        await query.message.reply_text(f"Noto‘g‘ri javob. To‘g‘ri javob: {correct_answer}. Qayta urinish uchun /quiz bosing.")

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot webhook o‘rnatilmoqda...")
    await app.bot.set_webhook(url=f"{URL}/telegram")
    await app.run_webhook(
        listen="0.0.0.0",
        port=443,
        url_path="/telegram",
        webhook_url=f"{URL}/telegram"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())