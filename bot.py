import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from PIL import Image
import pytesseract
import speech_recognition as sr
from gtts import gTTS
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
DEEPSEEK_API_KEY = "sk-029849f1e50248c0bfbf757b55723378"
TELEGRAM_BOT_TOKEN = "7631499563:AAE3Mw3WY-05k3jiHxxUGElLCdII5YwbCKU"
ADMIN_USER_ID = "1931103339"  # For admin commands

# Database setup
def init_db():
    conn = sqlite3.connect('education_bot.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, 
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      join_date TEXT,
                      last_active TEXT)''')
    
    # Create user preferences table
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_preferences
                     (user_id INTEGER PRIMARY KEY,
                      language TEXT DEFAULT 'bn',
                      level TEXT DEFAULT 'beginner',
                      favorite_subjects TEXT)''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# DeepSeek API function
def ask_deepseek(question, context=None):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [{"role": "user", "content": question}]
    if context:
        messages.insert(0, {"role": "system", "content": context})
    
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        return "দুঃখিত, আমি এখন আপনার প্রশ্নের উত্তর দিতে পারছি না। পরে আবার চেষ্টা করুন।"

# Image to text processing
def process_image(image_path):
    try:
        text = pytesseract.image_to_string(Image.open(image_path), lang='eng+ben')
        return text.strip() if text else "ছবি থেকে কোনো টেক্সট পড়া যায়নি।"
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        return "ছবি প্রসেস করতে সমস্যা হয়েছে।"

# Voice message processing
def process_voice(voice_path):
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(voice_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="bn-BD")
            return text
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        return None

# Text to speech conversion
def text_to_speech(text, lang='bn'):
    try:
        tts = gTTS(text=text, lang=lang)
        output_path = "response.mp3"
        tts.save(output_path)
        return output_path
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None

# Database functions
def update_user(update: Update):
    user = update.effective_user
    conn = sqlite3.connect('education_bot.db')
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute(
        '''INSERT OR REPLACE INTO users 
        (user_id, username, first_name, last_name, join_date, last_active) 
        VALUES (?, ?, ?, ?, COALESCE((SELECT join_date FROM users WHERE user_id=?), ?), ?)''',
        (user.id, user.username, user.first_name, user.last_name, user.id, now, now)
    )
    
    conn.commit()
    conn.close()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user(update)
    welcome_message = """
আসসালামু আলাইকুম! 👋

আমি আপনার ব্যক্তিগত এডুকেশন সহকারী বট। আপনি আমাকে যেকোনো বিষয়ে প্রশ্ন করতে পারেন:

- গণিত ও বিজ্ঞান
- ইতিহাস ও ভূগোল
- প্রোগ্রামিং ও প্রযুক্তি
- ভাষা শিক্ষা (ইংরেজি/বাংলা)

আপনি টেক্সট, ভয়েস মেসেজ বা এমনকি ছবি পাঠিয়েও প্রশ্ন করতে পারেন!

/help - সকল কমান্ড দেখুন
"""
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 সহায়িকা:

/start - বট শুরু করুন
/help - এই সহায়িকা দেখুন
/quiz [বিষয়] - কুইজ প্রশ্ন তৈরি করুন
/ask - সরাসরি প্রশ্ন করুন
/settings - আপনার সেটিংস পরিবর্তন করুন

আপনি সরাসরি যেকোনো প্রশ্ন লিখে বা ভয়েস মেসেজ পাঠাতে পারেন!
"""
    await update.message.reply_text(help_text)

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args) if context.args else "সাধারণ জ্ঞান"
    prompt = f"""
    ১০টি এমসিকিউ প্রশ্ন তৈরি করো {topic} বিষয়ে। 
    প্রতিটি প্রশ্নের জন্য:
    1. স্পষ্ট প্রশ্ন লিখ
    2. ৪টি অপশন দাও (a, b, c, d)
    3. সঠিক উত্তর নির্দেশ কর
    """
    
    quiz = ask_deepseek(prompt)
    await update.message.reply_text(f"📝 {topic} বিষয়ে কুইজ:\n\n{quiz}")

# Message handlers
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user(update)
    question = update.message.text
    
    # Check if it's a command (starts with /)
    if question.startswith('/'):
        return
    
    # Get user preferences from database
    conn = sqlite3.connect('education_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT language, level FROM user_preferences WHERE user_id=?", (update.effective_user.id,))
    prefs = cursor.fetchone()
    conn.close()
    
    language = prefs[0] if prefs else 'bn'
    level = prefs[1] if prefs else 'beginner'
    
    # Add context based on user level
    context_msg = f"User is a {level} level student. Provide detailed explanation in {language} language."
    answer = ask_deepseek(question, context_msg)
    
    await update.message.reply_text(answer)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user(update)
    try:
        # Download the image
        photo_file = await update.message.photo[-1].get_file()
        image_path = f"user_{update.effective_user.id}_image.jpg"
        await photo_file.download_to_drive(image_path)
        
        # Process the image
        text_from_image = process_image(image_path)
        
        if not text_from_image or "ছবি থেকে" in text_from_image:
            await update.message.reply_text("ছবি থেকে প্রশ্ন পড়তে পারিনি। সরাসরি টেক্সট লিখে পাঠান।")
            return
        
        await update.message.reply_text(f"📸 আপনার ছবি থেকে পড়া: {text_from_image}\n\nপ্রশ্নের উত্তর খুঁজছি...")
        
        # Get answer from DeepSeek
        answer = ask_deepseek(text_from_image)
        await update.message.reply_text(answer)
        
    except Exception as e:
        logger.error(f"Image handler error: {e}")
        await update.message.reply_text("ছবি প্রসেস করতে সমস্যা হয়েছে। আবার চেষ্টা করুন।")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user(update)
    try:
        # Download the voice message
        voice_file = await update.message.voice.get_file()
        voice_path = f"user_{update.effective_user.id}_voice.ogg"
        await voice_file.download_to_drive(voice_path)
        
        # Process the voice
        text_from_voice = process_voice(voice_path)
        
        if not text_from_voice:
            await update.message.reply_text("ভয়েস মেসেজ বুঝতে পারিনি। আবার চেষ্টা করুন।")
            return
        
        await update.message.reply_text(f"🎤 আপনার ভয়েস মেসেজ: {text_from_voice}\n\nপ্রশ্নের উত্তর খুঁজছি...")
        
        # Get answer from DeepSeek
        answer = ask_deepseek(text_from_voice)
        
        # Convert answer to speech
        speech_path = text_to_speech(answer)
        if speech_path:
            await update.message.reply_voice(voice=open(speech_path, 'rb'))
            os.remove(speech_path)
        else:
            await update.message.reply_text(answer)
            
    except Exception as e:
        logger.error(f"Voice handler error: {e}")
        await update.message.reply_text("ভয়েস মেসেজ প্রসেস করতে সমস্যা হয়েছে। আবার চেষ্টা করুন।")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    
    if update.effective_user:
        error_msg = "দুঃখিত, কোনো সমস্যা হয়েছে। দয়া করে পরে আবার চেষ্টা করুন।"
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=error_msg
        )

# Main function
def main():
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("quiz", quiz_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
