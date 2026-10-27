import sqlite3
import requests
import asyncio
from maxrubika import Bot, Messenger
from maxrubika.client.filters import IsMe
from rulog import Client as LoginClient

# ==========================================
# 1. تنظیمات (توکن رو اینجا بذار)
# ==========================================
BOT_TOKEN = "CCDEGH0ATOIFNDZSQUTOOBXGFHUFJWGKVDMGDIUMWCPDOXVLXQQNCVIFVCIAEKIM"
GROQ_API_KEY = "1xai-rlJOhherE5c6_nVm4zXUqvhehcigAFrE2j0uE4qlJBk"
SESSION_NAME = "KING Self"

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
bot = Bot(BOT_TOKEN)
app = None
pv_lock_active = False
muted_users = set()
login_sessions = {}

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
@bot.on_command("start")
async def start(bot, event):
    await event.reply(
        "🤖 **ربات کنترلر FKey**\n\n"
        "برای اتصال سلف‌بات به اکانت روبیکات، دستور `/login` رو بزن.\n"
        "بعد از لاگین، دستور `/panel` رو بزن تا پنل مدیریت باز بشه.\n"
        "برای راهنما، دستور `/help` رو بزن."
    )

@bot.on_command("login")
async def login_start(bot, event):
    user_id = str(event.sender_id)
    login_sessions[user_id] = {"step": "waiting_phone", "phone": None, "hash_code": None}
    await event.reply("📱 **لطفاً شماره تلفن خود را وارد کنید:**\n(مثال: `09123456789`)")

@bot.on_command("help")
async def help_cmd(bot, event):
    await event.reply(
        "📚 **راهنمای ربات:**\n\n"
        "`/login` - اتصال سلف‌بات\n"
        "`/panel` - پنل مدیریت\n"
        "`/help` - راهنما\n\n"
        "**دستورات سلف‌بات (بعد از لاگین):**\n"
        "`.save [یوزرنیم/آیدی]` - ذخیره کاربر\n"
        "`.info [یوزرنیم/آیدی]` - اطلاعات کاربر\n"
        "`.lock on/off` - قفل پیوی\n"
        "`.allow [یوزرنیم/آیدی]` - لیست سفید\n"
        "`.off_save [متن]` - ذخیره پیام آفلاین\n"
        "`.off_send [یوزرنیم/آیدی]` - ارسال پیام آفلاین\n"
        "ریپلای + `سکوت` - سکوت\n"
        "ریپلای + `حذف سکوت` - حذف سکوت"
    )

# ==========================================
# 6. هندلر پیام‌های ربات (لاگین)
# ==========================================
@bot.on_message()
async def handle_bot_message(bot, event):
    user_id = str(event.sender_id)
    text = event.text or ""

    if user_id not in login_sessions:
        return

    state = login_sessions[user_id]

    if state["step"] == "waiting_phone":
        phone = text.strip()
        if not phone.startswith("0") or len(phone) < 10:
            await event.reply("❌ شماره نامعتبر. با فرمت `09123456789` وارد کن.")
            return

        await event.reply("⏳ در حال ارسال کد تأیید...")
        try:
            login_client = LoginClient()
            hash_code = login_client.sendCode("android", phone, send_type=True)
            if not hash_code:
                hash_code = login_client.sendCode("web", phone)

            if hash_code:
                state["step"] = "waiting_code"
                state["phone"] = phone
                state["hash_code"] = hash_code
                await event.reply("🔢 **کد تأیید به گوشیت ارسال شد. کد رو وارد کن:**")
            else:
                await event.reply("❌ ارسال کد ناموفق بود. دوباره تلاش کن.")
                del login_sessions[user_id]
        except Exception as e:
            await event.reply(f"❌ خطا: {e}")
            del login_sessions[user_id]

    elif state["step"] == "waiting_code":
        code = text.strip()
        try:
            login_client = LoginClient()
            login_response = login_client.signIn("android", state["phone"], state["hash_code"], code)

            if login_response:
                login_client.register(platform="android", auths=login_response['Auth'], keys=login_response['Key'])
                await event.reply("✅ **لاگین موفق!** سلف‌بات در حال راه‌اندازی...")

                global app
                app = Messenger(SESSION_NAME)
                setup_selfbot_handlers(app)
                asyncio.create_task(app.start())

                await event.reply("🎉 **سلف‌بات فعال شد!**\n\n`/panel` رو بزن.")
                del login_sessions[user_id]
            else:
                await event.reply("❌ کد نامعتبر. دوباره تلاش کن.")
        except Exception as e:
            await event.reply(f"❌ خطا: {e}")

# ==========================================
# 7. هندلر سلف‌بات
# ==========================================
def setup_selfbot_handlers(messenger):
    @messenger.on_new_message()
    async def self_handler(event):
        global pv_lock_active
        text = event.text or ""
        sender_id = str(event.author_guid)
        is_me = (sender_id == str(messenger.me.id))
        chat_type = getattr(event, 'chat_type', 'Unknown')

        if is_me:
            if text.startswith(".save "):
                target = text.split(" ", 1)[1].strip()
                try:
                    user = messenger.get_user_info(target)
                    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)", 
                                   (str(user.id), user.username, getattr(user, 'phone', ''), user.first_name))
                    conn.commit()
                    await event.reply(f"✅ {user.first_name} ذخیره شد.")
                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

            elif text == ".lock on":
                pv_lock_active = True
                await event.reply("🔒 قفل پیوی فعال شد.")
            elif text == ".lock off":
                pv_lock_active = False
                await event.reply("🔓 قفل پیوی غیرفعال شد.")

            elif text.startswith(".allow "):
                target = text.split(" ", 1)[1].strip()
                try:
                    user = messenger.get_user_info(target)
                    cursor.execute("INSERT OR REPLACE INTO whitelist VALUES (?)", (str(user.id),))
                    conn.commit()
                    await event.reply(f"✅ {user.first_name} به لیست سفید اضافه شد.")
                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

            elif text.startswith(".off_save "):
                msg_text = text.replace(".off_save ", "")
                cursor.execute("INSERT INTO offline_msgs (text) VALUES (?)", (msg_text,))
                conn.commit()
                await event.reply("✅ پیام آفلاین ذخیره شد.")

            elif text.startswith(".off_send "):
                target = text.split(" ", 1)[1].strip()
                cursor.execute("SELECT text FROM offline_msgs ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    messenger.send_message(target, row[0])
                    await event.reply("✅ ارسال شد.")
                else:
                    await event.reply("❌ پیام آفلاینی نیست.")

            elif text.startswith(".info "):
                target = text.split(" ", 1)[1].strip()
                try:
                    user = messenger.get_user_info(target)
                    await event.reply(f"👤 {user.first_name}\n🆔 `{user.id}`\n📛 @{getattr(user, 'username', 'ندارد')}")
                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")
            return

        if event.reply_to_message and is_me:
            if event.text == "سکوت":
                muted_users.add(str(event.reply_to_message.author_guid))
                await event.reply("🔇 سکوت شد.")
                return
            elif event.text == "حذف سکوت":
                muted_users.discard(str(event.reply_to_message.author_guid))
                await event.reply("🔊 خارج شد.")
                return

        if sender_id in muted_users:
            return

        if pv_lock_active and chat_type == "PV":
            cursor.execute("SELECT user_id FROM whitelist WHERE user_id = ?", (sender_id,))
            if not cursor.fetchone():
                try:
                    messenger.delete_messages(event.chat_id, [event.id], type="Global")
                except:
                    pass
                return

        if chat_type == "PV" and not is_me and event.text:
            ai = get_ai_response(event.text)
            messenger.send_message(event.chat_id, ai)

# ==========================================
# 8. اجرا
# ==========================================
if __name__ == "__main__":
    print("🚀 ربات کنترلر روشن شد...")
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 ربات متوقف شد.")
    except Exception as e:
        print(f"❌ خطا: {e}")
