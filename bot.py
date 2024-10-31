# bot.py

import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_TOKEN, MONGO_URI, BONUS_COINS, STREAK_BONUS_COINS, BONUS_INTERVAL, \
                   RARITY_LEVELS, RARITY_WEIGHTS, MESSAGE_THRESHOLD, BOT_OWNER_ID

# Initialize bot and MongoDB client
bot = telebot.TeleBot(API_TOKEN)
client = MongoClient(MONGO_URI)
db = client['philo_game']
users_collection = db['users']
characters_collection = db['characters']
groups_collection = db['groups']
sudo_users_collection = db['sudo_users']  # Collection for storing sudo users

# Initialize sudo users
SUDO_USERS = 7222795580  # Start with the bot owner as a sudo user

# Load sudo users from the database
def load_sudo_users():
    sudo_users = sudo_users_collection.find()
    for user in sudo_users:
        SUDO_USERS.add(user['user_id'])

load_sudo_users()

### Database Functions ###
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
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

### Command Handlers ###
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    get_user_data(user_id)

    welcome_message = """
✿︎ <b>Wᴇʟᴄᴏᴍᴇ ᴛᴏ Pʜɪʟᴏ Gᴀᴍᴇ</b> ✿︎

ꜱᴛᴀʀᴛ ᴄᴏʟʟᴇᴄᴛɪɴɢ ᴀɴᴅ ɢᴜᴇꜱꜱɪɴɢ ᴀɴɪᴍᴇ ᴄʜᴀʀᴀᴄᴛᴇʀꜱ!

ᴜꜱᴇ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅꜱ ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ ᴀʟʟ ᴛʜᴇ ꜰᴇᴀᴛᴜʀᴇꜱ!
"""
    markup = InlineKeyboardMarkup()
    developer_button = InlineKeyboardButton(text="Developer", url="https://t.me/TechPiro")
    markup.add(developer_button)
    bot.send_message(message.chat.id, welcome_message, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
<b>✿︎ Pʜɪʟᴏ Gᴀᴍᴇ Cᴏᴍᴍᴀɴᴅꜱ ✿︎</b>

<b>General Commands:</b>
/start - Start the bot and get a welcome message
/bonus - Claim your daily bonus
/profile - View your profile and stats
/topcoins - Show the top 10 users by coins

<b>Owner and Sudo Commands:</b>
/stats - View bot statistics (Owner only)
/add - Add a sudo user by ID (Owner only)
/upload - Upload a new character (Sudo only, rarity is auto-assigned)
"""
    bot.reply_to(message, help_text, parse_mode='HTML')

@bot.message_handler(commands=['add'])
def add_sudo_user(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "🚫 You are not authorized to use this command.")
        return

    try:
        new_sudo_id = int(message.text.split()[1])
        if new_sudo_id in SUDO_USERS:
            bot.reply_to(message, "🚫 This user is already a sudo user.")
            return

        SUDO_USERS.add(new_sudo_id)
        sudo_users_collection.insert_one({'user_id': new_sudo_id})
        bot.reply_to(message, f"✅ User {new_sudo_id} has been added as a sudo user.")
    except (IndexError, ValueError):
        bot.reply_to(message, "🚫 Invalid format. Use: /add <user_id>")

@bot.message_handler(commands=['bonus'])
def bonus_command(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)

    current_time = datetime.now()
    if user['last_bonus']:
        time_since_last_bonus = current_time - user['last_bonus']
        if time_since_last_bonus < BONUS_INTERVAL:
            time_remaining = BONUS_INTERVAL - time_since_last_bonus
            hours, remainder = divmod(time_remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            bot.reply_to(message, f"⏳ You've already claimed your bonus today! Come back in {hours} hours and {minutes} minutes.")
            return

    new_coins = user['coins'] + BONUS_COINS
    user['streak'] += 1
    streak_bonus = STREAK_BONUS_COINS * user['streak']

    update_user_data(user_id, {
        'coins': new_coins + streak_bonus,
        'last_bonus': current_time,
        'streak': user['streak']
    })

    bot.reply_to(message, f"🎁 You have claimed your daily bonus of {BONUS_COINS} coins!\n🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-day streak!")

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    profile_message = (
        f"✿︎ <b>{user['profile'] if user['profile'] else 'User Profile'}</b> ✿︎\n\n"
        f"💰 <b>Coins:</b> {user['coins']}\n"
        f"🎯 <b>Correct Guesses:</b> {user['correct_guesses']}\n"
        f"🔥 <b>Streak:</b> {user['streak']}\n"
    )
    bot.send_message(message.chat.id, profile_message, parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def show_bot_stats(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "🚫 You are not authorized to use this command.")
        return

    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    total_groups = groups_collection.count_documents({})

    bot.reply_to(message, f"📊 <b>Bot Stats:</b>\n"
                          f"👥 Total Users: {total_users}\n"
                          f"🎭 Total Characters: {total_characters}\n"
                          f"💬 Total Groups: {total_groups}", parse_mode='HTML')

@bot.message_handler(commands=['topcoins'])
def topcoins_command(message):
    top_users = users_collection.find().sort('coins', -1).limit(10)
    leaderboard = "🏆 <b>Top 10 Users by Coins:</b>\n\n"
    for i, user in enumerate(top_users, start=1):
        leaderboard += f"{i}. {user['profile'] if user['profile'] else 'User'} - {user['coins']} coins\n"

    bot.send_message(message.chat.id, leaderboard, parse_mode='HTML')

@bot.message_handler(commands=['upload'])
def upload_command(message):
    if message.from_user.id not in SUDO_USERS:
        bot.reply_to(message, "🚫 You are not authorized to use this command.")
        return

    try:
        args = message.text.split(maxsplit=2)
        image_url, character_name = args[1], args[2]
        rarity = assign_rarity()  # Auto-assign rarity

        character_id = characters_collection.count_documents({}) + 1
        new_character = {
            'id': character_id,
            'image_url': image_url,
            'character_name': character_name,
            'rarity': rarity
        }
        characters_collection.insert_one(new_character)
        
        bot.reply_to(message, f"✅ Character '{character_name}' added successfully with {RARITY_LEVELS[rarity]} rarity.")
    except (IndexError, ValueError):
        bot.reply_to(message, "🚫 Incorrect format. Use: /upload <image_url> <character_name>")

# Handle all messages to manage game logic
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_character, global_message_count

    if message.chat.type in ['group', 'supergroup']:
        global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(message.chat.id)
        global_message_count = 0

    user_guess = message.text.strip().lower() if message.text else ""
    if current_character and user_guess in current_character['character_name'].strip().lower():
        user_id = message.from_user.id
        user = get_user_data(user_id)
        new_coins = user['coins'] + 50  # Award for correct guess
        user['streak'] += 1
        streak_bonus = STREAK_BONUS_COINS * user['streak']

        update_user_data(user_id, {
            'coins': new_coins + streak_bonus,
            'correct_guesses': user['correct_guesses'] + 1,
            'streak': user['streak'],
        })

        bot.reply_to(message, f"🎉 Correct! You earned 50 coins!\n🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-guess streak!")
        send_character(message.chat.id)

# Start polling
if __name__ == "__main__":
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
