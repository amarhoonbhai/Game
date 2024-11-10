import os
import random
from datetime import datetime, timedelta
from pymongo import MongoClient, errors
from telebot import TeleBot, types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))
CHARACTER_CHANNEL_ID = int(os.getenv("CHARACTER_CHANNEL_ID"))
BONUS_COINS = int(os.getenv("BONUS_COINS"))
STREAK_BONUS_COINS = int(os.getenv("STREAK_BONUS_COINS"))
COINS_PER_GUESS = int(os.getenv("COINS_PER_GUESS"))
MESSAGE_THRESHOLD = int(os.getenv("MESSAGE_THRESHOLD"))
TOP_LEADERBOARD_LIMIT = int(os.getenv("TOP_LEADERBOARD_LIMIT"))

# Initialize bot and MongoDB
bot = TeleBot(API_TOKEN)

try:
    client = MongoClient(MONGO_URI)
    db = client['philo_game']
    users_collection = db['users']
    characters_collection = db['characters']
    sudo_users_collection = db['sudo_users']  # Collection to manage sudo users
    print("✅ Connected to MongoDB successfully.")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# Track messages and character
current_character = None
global_message_count = 0

# Utility Functions
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
            'profile_name': ""
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def assign_rarity():
    rarity_levels = {'Common': '⭐', 'Rare': '🌟', 'Epic': '💎', 'Legendary': '✨'}
    weights = [60, 25, 10, 5]
    return random.choices(list(rarity_levels.keys()), weights=weights, k=1)[0]

def fetch_new_character():
    characters = list(characters_collection.find())
    return random.choice(characters) if characters else None

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    user_name = message.from_user.full_name
    update_user_data(user_id, {'profile_name': user_name})
    bot.reply_to(message, f"🎉 Welcome to Philo Game, {user_name}! 🎮 Use /help to see available commands.")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
/start - Welcome message and profile creation
/bonus - Claim daily bonus coins
/profile - View your stats and game progress
/levels - Show top players by coins
/stats - Show bot statistics
/upload <image_url> <character_name> - Upload a new character (admin only)
/addsudo <user_id> - Add a new sudo user (admin only)
"""
    bot.reply_to(message, help_message)

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    now = datetime.now()

    if user['last_bonus']:
        time_since_bonus = now - user['last_bonus']
        if time_since_bonus < timedelta(days=1):
            time_left = timedelta(days=1) - time_since_bonus
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            bot.reply_to(message, f"⏳ Come back in {hours}h {minutes}m for your next bonus!")
            return

    new_coins = user['coins'] + BONUS_COINS + (user['streak'] * STREAK_BONUS_COINS)
    update_user_data(user_id, {
        'coins': new_coins,
        'last_bonus': now,
        'streak': user['streak'] + 1
    })
    bot.reply_to(message, f"💰 You received {BONUS_COINS} coins and a streak bonus! Total coins: {new_coins}.")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    profile_text = (
        f"👤 <b>Profile of {user['profile_name']}</b>\n"
        f"💰 Coins: {user['coins']}\n"
        f"🎯 Correct Guesses: {user['correct_guesses']}\n"
        f"🔥 Streak: {user['streak']}\n"
    )
    bot.reply_to(message, profile_text, parse_mode='HTML')

@bot.message_handler(commands=['levels'])
def show_levels(message):
    top_users = users_collection.find().sort("coins", -1).limit(TOP_LEADERBOARD_LIMIT)
    leaderboard = "🏆 <b>Top Players</b> 🏆\n\n"
    for i, user in enumerate(top_users, 1):
        leaderboard += f"{i}. {user['profile_name']} - {user['coins']} coins\n"
    bot.reply_to(message, leaderboard, parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def show_stats(message):
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    bot.reply_to(
        message,
        f"📊 Bot Stats:\n👥 Total Users: {total_users}\n🎭 Characters: {total_characters}"
    )

# Check if user is sudo
def is_sudo_user(user_id):
    return sudo_users_collection.find_one({"user_id": user_id}) is not None

# Adding a sudo user
@bot.message_handler(commands=['addsudo'])
def add_sudo_user(message):
    user_id = message.from_user.id
    if user_id == BOT_OWNER_ID:
        msg_parts = message.text.split()
        if len(msg_parts) == 2:
            try:
                sudo_user_id = int(msg_parts[1])
                sudo_users_collection.insert_one({"user_id": sudo_user_id})
                bot.reply_to(message, f"✅ Added user {sudo_user_id} as sudo.")
            except ValueError:
                bot.reply_to(message, "🚫 Invalid user ID format.")
        else:
            bot.reply_to(message, "Usage: /addsudo <user_id>")
    else:
        bot.reply_to(message, "🚫 You don't have permission to use this command.")

# Upload a character (for bot owner or sudo users)
@bot.message_handler(commands=['upload'])
def upload_character(message):
    user_id = message.from_user.id
    if user_id == BOT_OWNER_ID or is_sudo_user(user_id):
        msg_parts = message.text.split(maxsplit=2)
        if len(msg_parts) == 3:
            image_url, character_name = msg_parts[1], msg_parts[2]
            characters_collection.insert_one({
                'image_url': image_url,
                'character_name': character_name,
                'rarity': assign_rarity()
            })
            bot.reply_to(message, "✅ Character uploaded successfully!")
        else:
            bot.reply_to(message, "Usage: /upload <image_url> <character_name>")
    else:
        bot.reply_to(message, "🚫 You don't have permission to use this command.")

# Start bot polling
bot.infinity_polling(timeout=60, long_polling_timeout=60)
