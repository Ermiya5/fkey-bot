import sqlite3
import requests
from rubiko import RubikaBot

# ==========================================
# 1. تنظیمات
# ==========================================
BOT_TOKEN = "CCDEGH0ATOIFNDZSQUTOOBXGFHUFJWGKVDMGDIUMWCPDOXVLXQQNCVIFVCIAEKIM"
GROQ_API_KEY = "1xai-rlJOhherE5c6_nVm4zXUqvhehcigAFrE2j0uE4qlJBk"

# ==========================================
# 2. دیتابیس
# ==========================================
conn = sqlite3.connect('selfbot.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id TEXT PRIMARY KEY, username TEXT, phone TEXT, first_name TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS offline_msgs 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS whitelist (user_id TEXT PRIMARY KEY)''')
conn.commit()

# ==========================================
# 3. راه‌اندازی ربات
# ==========================================
bot = RubikaBot(BOT_TOKEN)
pv_lock_active = False
muted_users = set()

# ==========================================
# 4. هوش مصنوعی
# ==========================================
def get_ai_response(text):
    if not GROQ_API_KEY:
        return "❌ کلید هوش مصنوعی تنظیم نشده."
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama3-8b-8192", "messages": [{"role": "user", "content": text}]}
        res = requests.post(url, headers=headers, json=data, timeout=10)
        return res.json()['choices'][0]['message']['content']
    except Exception:
        return "❌ الان نمی‌تونم جواب بدم."

# ==========================================
# 5. دستورات ربات
# ==========================================
@bot.on_message()
def handler(bot, message):
    global pv_lock_active
    text = message.text or ""
    chat_id = message.chat_id

    # دستور /start
    if text == "/start":
        bot.send_message(chat_id, "🤖 ربات فعاله!\n\nدستورات:\n`.lock on/off` - قفل پیوی\n`.save [آیدی]` - ذخیره کاربر\n`.off_save [متن]` - ذخیره پیام آفلاین")
    
    # قفل پیوی
    elif text == ".lock on":
        pv_lock_active = True
        bot.send_message(chat_id, "🔒 قفل پیوی فعال شد.")
    elif text == ".lock off":
        pv_lock_active = False
        bot.send_message(chat_id, "🔓 قفل پیوی غیرفعال شد.")
    
    # ذخیره کاربر
    elif text.startswith(".save "):
        target = text.replace(".save ", "").strip()
        try:
            user = bot.get_user_info(target)
            cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)", 
                           (str(user.id), user.username, getattr(user, 'phone', ''), user.first_name))
            conn.commit()
            bot.send_message(chat_id, f"✅ {user.first_name} ذخیره شد.")
        except Exception as e:
            bot.send_message(chat_id, f"❌ خطا: {e}")
    
    # پیام آفلاین
    elif text.startswith(".off_save "):
        msg_text = text.replace(".off_save ", "")
        cursor.execute("INSERT INTO offline_msgs (text) VALUES (?)", (msg_text,))
        conn.commit()
        bot.send_message(chat_id, "✅ پیام آفلاین ذخیره شد.")
    
    elif text.startswith(".off_send "):
        target = text.replace(".off_send ", "").strip()
        cursor.execute("SELECT text FROM offline_msgs ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            bot.send_message(target, row[0])
            bot.send_message(chat_id, "✅ ارسال شد.")
        else:
            bot.send_message(chat_id, "❌ پیام آفلاینی نیست.")
    
    # قفل پیوی (برای پیام‌های دریافتی)
    elif pv_lock_active and message.chat_type == "PV":
        cursor.execute("SELECT user_id FROM whitelist WHERE user_id = ?", (str(message.sender_id),))
        if not cursor.fetchone():
            try:
                bot.delete_message(chat_id, message.id)
            except:
                pass
            return
    
    # هوش مصنوعی (توی PV)
    elif message.chat_type == "PV" and text:
        ai = get_ai_response(text)
        bot.send_message(chat_id, ai)

# ==========================================
# 6. اجرا
# ==========================================
if __name__ == "__main__":
    print("🚀 ربات روشن شد...")
    bot.run()
