
TOKEN = 'Input your TOKEN'

import os
import urllib.request
import cv2
import sqlite3
import numpy as np
import soundfile as sf
from telegram.ext import Application, MessageHandler, filters
import requests



if not os.path.exists('photos'):
    os.makedirs('photos')

if not os.path.exists('audio'):
    os.makedirs('audio')

conn = sqlite3.connect('TelegramBotDB.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS Photos 
                  (id INTEGER PRIMARY KEY, user_id INTEGER, chat_id INTEGER, photo_number INTEGER, file_name TEXT, file_path TEXT, has_face INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS AudioMessages
                  (id INTEGER PRIMARY KEY, user_id INTEGER, chat_id INTEGER, audio_number INTEGER, file_name TEXT, file_path TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS DialogueCounters 
                  (chat_id INTEGER PRIMARY KEY, last_photo_number INTEGER DEFAULT 0, last_audio_number INTEGER DEFAULT 0)''')

conn.commit()


async def check_for_human_face(file_id, context):
    file_info = await context.bot.get_file(file_id)
    file_url = file_info.file_path
    response = requests.get(file_url)
    img = np.asarray(bytearray(response.content), dtype="uint8")
    img = cv2.imdecode(img, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return len(faces) > 0


async def handling_photo_message(update, context):
    file_id = update.message.photo[-1]['file_id']
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    has_face = await check_for_human_face(file_id, context)
    if has_face:
        await update.message.reply_text("Face detected. The photo will be saved.")
        file_info = await context.bot.get_file(file_id)
        file_url = file_info.file_path
        cursor.execute("SELECT last_photo_number FROM DialogueCounters WHERE chat_id = ?", (chat_id,))
        last_photo_number = cursor.fetchone()
        if last_photo_number:
            photo_number = last_photo_number[0] + 1
        else:
            photo_number = 1
        filename = f"{user_id}_photo_{photo_number}.jpg"
        unique_filename = os.path.join('photos', filename)
        urllib.request.urlretrieve(file_url, unique_filename)
        cursor.execute("INSERT INTO Photos (user_id, chat_id, photo_number, file_name, file_path, has_face) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, chat_id, photo_number, filename, unique_filename, has_face))
        cursor.execute("INSERT OR REPLACE INTO DialogueCounters (chat_id, last_photo_number) VALUES (?, ?)",
                       (chat_id, photo_number))
        conn.commit()
    else:
        await update.message.reply_text("No face detected. The photo will not be saved.")


async def handle_audio_message(update, context):
    if update.message.voice:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id
        file_id = update.message.voice.file_id
        file_info = await context.bot.get_file(file_id)
        file_path = file_info.file_path

        cursor.execute("SELECT last_audio_number FROM DialogueCounters WHERE chat_id = ?", (chat_id,))
        last_audio_number = cursor.fetchone()
        if last_audio_number:
            audio_number = last_audio_number[0] + 1
        else:
            audio_number = 1

        filename = f"{user_id}_audio_{audio_number}.wav"
        wav_filename = os.path.join('audio', filename)
        urllib.request.urlretrieve(file_path, file_id)
        convert_to_wav(file_id, wav_filename)
        os.remove(file_id)
        cursor.execute("INSERT INTO AudioMessages (user_id, chat_id, audio_number, file_name, file_path) VALUES (?, ?, ?, ?, ?)",
                       (user_id, chat_id, audio_number, filename, wav_filename))
        cursor.execute("INSERT OR REPLACE INTO DialogueCounters (chat_id, last_audio_number) VALUES (?, ?)",
                       (chat_id, audio_number))

        conn.commit()
        await update.message.reply_text("Voice message saved.")


async def start_commmand(update, context):
    await update.message.reply_text('Hello! Welcome To Store!')


def convert_to_wav(input_file, output_file):
    data, samplerate = sf.read(input_file)
    sf.write(output_file, data, samplerate, format='WAV', subtype='PCM_16')


if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()

    application.add_handler(MessageHandler(filters.PHOTO, handling_photo_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_audio_message))
    application.add_handler(MessageHandler(filters.COMMAND, start_commmand))

    application.run_polling(1.0)