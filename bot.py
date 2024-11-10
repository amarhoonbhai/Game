import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bot Token and MongoDB URI
API_TOKEN = "7579121046:AAEc0CkNM3hjKtneFRNaU4bXIa3yueRyHFM"
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"

# Admin and Channel Information
BOT_OWNER_ID = 7222795580
CHANNEL_ID = -1002438449944

# Bot Initialization
bot = telebot.TeleBot(API_TOKEN)

# MongoDB Connection
try:
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']
    users_collection = db['users']
    characters_collection = db['characters']
    groups_collection = db['groups']
    print("✅ MongoDB connected successfully.")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# Settings
BONUS_COINS = 5000
BONUS_INTERVAL = timedelta(days=1)
COINS_PER_GUESS = 50
LEVEL_INCREMENT = 5
STREAK_BONUS_COINS = 1000
RARITY_LEVELS = {'Common': '⭐', 'Rare': '🌟', 'Epic': '💎', 'Legendary': '✨'}
RARITY_WEIGHTS = [60, 25, 10, 5]
MESSAGE_THRESHOLD = 5

# Sudo Users
SUDO_USERS = [BOT_OWNER_ID]

# Global variables to track the current character and message count
current_character = None
global_message_count = 0  # Global counter for messages in all chats

# Helper Functions
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if not user:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'inventory': [],
            'last_bonus': None,
            'streak': 0,
            'profile': None
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    characters = list(characters_collection.find())
    return random.choice(characters) if characters else None

def get_user_level(correct_guesses):
    return (correct_guesses // LEVEL_INCREMENT) + 1

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    profile_name = message.from_user.full_name
    if not user['profile']:
        update_user_data(user_id, {'profile': profile_name})

    welcome_message = """
<b>🎮 Welcome to Philo Game! 🎮</b>

Prepare to dive into the ultimate anime character guessing game! ✨ Collect rare characters, climb the leaderboard, and show off your anime knowledge. 🌟

Use <b>/help</b> to see all the commands and start your journey. Have fun and good luck on your adventure! 🏆
"""
    markup = InlineKeyboardMarkup()
    developer_button = InlineKeyboardButton(text="👨‍💻 Developer - @TechPiro", url="https://t.me/TechPiro")
    markup.add(developer_button)

    bot.send_message(message.chat.id, welcome_message, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
<b>💡 Available Commands 💡</b>
/bonus - Claim your daily bonus 💰
/stats - Show bot stats 📊
/profile - View your profile 📋
/levels - Show top users by level 🏆
/addsudo [user_id] - Add sudo user (Admin only) 🔧
/upload [image_url] [character_name] - Upload a character (Sudo only) 🖼️
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    current_time = datetime.now()

    if user['last_bonus']:
        time_since_last_bonus = current_time - user['last_bonus']
        if time_since_last_bonus < BONUS_INTERVAL:
            remaining_time = BONUS_INTERVAL - time_since_last_bonus
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            bot.reply_to(message, f"🕒 Bonus already claimed! Try again in {hours}h {minutes}m.")
            return

    new_coins = user['coins'] + BONUS_COINS
    user['streak'] += 1
    streak_bonus = STREAK_BONUS_COINS * user['streak']
    update_user_data(user_id, {
        'coins': new_coins + streak_bonus,
        'last_bonus': current_time,
        'streak': user['streak']
    })

    bot.reply_to(message, f"🎉 You claimed {BONUS_COINS} coins!\n🔥 Streak Bonus: {streak_bonus} coins!")

@bot.message_handler(commands=['stats'])
def show_bot_stats(message):
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    total_groups = groups_collection.count_documents({})

    bot.reply_to(message, f"<b>📊 Bot Stats 📊</b>\n\n"
                          f"👥 Total Users: {total_users}\n"
                          f"🌌 Total Characters: {total_characters}\n"
                          f"💬 Total Groups: {total_groups}", parse_mode='HTML')

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    level = get_user_level(user['correct_guesses'])
    
    profile_message = (f"<b>👤 Profile of {user['profile']} 👤</b>\n\n"
                       f"💰 Coins: {user['coins']}\n"
                       f"🎖️ Level: {level}\n"
                       f"🔥 Streak: {user['streak']} days\n"
                       f"✅ Correct Guesses: {user['correct_guesses']}")
    bot.reply_to(message, profile_message, parse_mode='HTML')

@bot.message_handler(commands=['levels'])
def show_top_levels(message):
    top_users = users_collection.find().sort("correct_guesses", -1).limit(10)
    levels_message = "<b>🏆 Top Users by Level 🏆</b>\n\n"
    for i, user in enumerate(top_users, start=1):
        level = get_user_level(user['correct_guesses'])
        profile_name = user['profile'] if user['profile'] else "Unknown User"
        levels_message += f"{i}. {profile_name} - Level {level} 🎖️\n"
    bot.reply_to(message, levels_message, parse_mode='HTML')

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if message.from_user.id not in SUDO_USERS:
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
        rarity = assign_rarity()
        character = {'image_url': image_url, 'character_name': character_name, 'rarity': rarity}
        characters_collection.insert_one(character)
        bot.reply_to(message, f"✅ Character '{character_name}' added with rarity '{rarity}'!")
    except ValueError:
        bot.reply_to(message, "⚠️ Please use the format: /upload [image_url] [character_name]")

@bot.message_handler(commands=['addsudo'])
def add_sudo_user(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "❌ Only the bot owner can add sudo users.")
        return

    try:
        _, new_sudo_id = message.text.split()
        new_sudo_id = int(new_sudo_id)
        if new_sudo_id not in SUDO_USERS:
            SUDO_USERS.append(new_sudo_id)
            bot.reply_to(message, f"✅ User ID {new_sudo_id} added as sudo user.")
        else:
            bot.reply_to(message, f"⚠️ User ID {new_sudo_id} is already a sudo user.")
    except (ValueError, IndexError):
        bot.reply_to(message, "⚠️ Please provide a valid user ID to add as sudo.")

# Handle All Messages and Check for Character Guesses
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_character
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_guess = message.text.strip().lower() if message.text else ""
    global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(chat_id)
        global_message_count = 0

    if current_character and user_guess:
        character_name = current_character['character_name'].strip().lower()
        if user_guess in character_name:
            user = get_user_data(user_id)
            new_coins = user['coins'] + COINS_PER_GUESS
            user['correct_guesses'] += 1
            level = get_user_level(user['correct_guesses'])
            update_user_data(user_id, {'coins': new_coins, 'correct_guesses': user['correct_guesses']})

            correct_guess_captions = [
                "🎉 Amazing! You've guessed correctly!",
                "✨ You're on fire! Another correct guess!",
                "💯 You're unstoppable!",
                "🔥 Right on! You nailed it!",
                "🎊 Another one for your collection!",
                "👏 Great job, you guessed it!",
                "🥳 Bingo! You're amazing!"
            ]
            bot.reply_to(message, random.choice(correct_guess_captions) + f" You earned {COINS_PER_GUESS} coins! 🎖️ Level {level}")
            send_character(chat_id)

# Send Random Character to Chat
def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = f"🔍 Guess the Character!\n🌠 Rarity: {rarity}\n🎭 Name: ???"
        bot.send_photo(chat_id, current_character['image_url'], caption=caption)

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
