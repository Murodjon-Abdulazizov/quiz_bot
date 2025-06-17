import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN is missing. Check your .env or environment variables.")


import os
from dotenv import load_dotenv

import logging
import random
import asyncio
import os
from telegram import Update, Poll
from telegram.ext import (
    ApplicationBuilder, CommandHandler, PollAnswerHandler,
    ContextTypes
)

# 1. Logging (xatoliklar uchun)
logging.basicConfig(level=logging.INFO)

# 2. Foydalanuvchi test holati
user_data = {}

# 3. TXT fayldan savollarni JSON formatga o‘tkazish
def parse_txt_to_json(txt_path):
    questions = []
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    i = 0
    while i < len(lines):
        try:
            question = lines[i]
            options = [
                lines[i+1][3:],  # A)
                lines[i+2][3:],  # B)
                lines[i+3][3:],  # C)
                lines[i+4][3:]   # D)
            ]
            correct_letter = lines[i+5].split(":")[1].strip().upper()
            correct_index = {'A': 0, 'B': 1, 'C': 2, 'D': 3}[correct_letter]

            questions.append({
                "question": question,
                "options": options,
                "correct_option_id": correct_index
            })
            i += 6
        except Exception as e:
            print(f"Xatolik {i}-qatorda: {e}")
            break
    return questions

# 4. /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not os.path.exists("questions.txt"):
        await update.message.reply_text("❌ questions.txt fayli topilmadi. Faylni bot papkasiga joylashtiring.")
        return

    all_questions = parse_txt_to_json("questions.txt")
    if not all_questions:
        await update.message.reply_text("❗ Fayl bo‘sh yoki noto‘g‘ri formatda.")
        return

    random.shuffle(all_questions)
    user_data[user_id] = {
        "index": 0,
        "correct": 0,
        "questions": all_questions
    }
    await send_poll(update, context)

# 5. Poll yuborish
async def send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_data[user_id]
    index = state["index"]
    questions = state["questions"]

    if index < len(questions):
        q = questions[index]
        poll_msg = await context.bot.send_poll(
            chat_id=update.effective_chat.id,
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

        if percent >= 86:
            mark = 5
        elif percent >= 71:
            mark = 4
        elif percent >= 50:
            mark = 3
        else:
            mark = 2

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"✅ Test yakunlandi!\n"
                f"To‘g‘ri javoblar: {correct}/{total}\n"
                f"Natija: {percent}%\n"
                f"Bahoyingiz: {mark}"
            )
        )

# 6. Poll javobi kelganda ishlaydi
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    user_id = context.bot_data.get(poll_id)

    if user_id is None or user_id not in user_data:
        return

    state = user_data[user_id]
    index = state["index"]
    questions = state["questions"]

    if index < len(questions):
        correct_id = questions[index]["correct_option_id"]
        if update.poll_answer.option_ids[0] == correct_id:
            state["correct"] += 1
        state["index"] += 1

        await asyncio.sleep(1.5)  # Delay to let poll close

        class DummyUpdate:
            def __init__(self, uid, cid):
                self.effective_user = type("User", (), {"id": uid})
                self.effective_chat = type("Chat", (), {"id": cid})
        dummy = DummyUpdate(user_id, update.poll_answer.user.id)
        await send_poll(dummy, context)

# 7. Bot token va ishga tushirish
BOT_TOKEN = "7853394479:AAEJYVirasfuic3cM6MoRPAHH99LUoB2T2A"

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(PollAnswerHandler(handle_poll_answer))

app.run_polling()
