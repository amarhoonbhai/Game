import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAFlFhjpuNiyQ-sEVDUKCYVc0x4leNfwCFY"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
try:
    MONGO_URI = "mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    groups_collection = db['groups']  # Collection for group stats
    print("🝮︎︎︎ Connected to MongoDB 🝮︎︎︎")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# List of sudo users (user IDs)
SUDO_USERS = [BOT_OWNER_ID, 6180999156]  # Add user IDs of sudo users here

bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 50000  # Bonus amount for daily claim
BONUS_INTERVAL = timedelta(days=1)  # Bonus claim interval (24 hours)
COINS_PER_GUESS = 50  # Coins for correct guesses
STREAK_BONUS_COINS = 1000  # Additional coins for continuing a streak
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character
TOP_LEADERBOARD_LIMIT = 10  # Limit for leaderboard to only show top 10 users
ITEMS_PER_PAGE = 20  # Number of characters per page in inventory

# Global variables to track the current character and message count
current_character = None
global_message_count = 0  # Global counter for messages in all chats

# Helper Functions
def get_user_data(user_id):
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user is None:
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
    except Exception as e:
        print(f"Error in get_user_data: {e}")
        return None

def update_user_data(user_id, update_data):
    try:
        users_collection.update_one({'user_id': user_id}, {'$set': update_data})
    except Exception as e:
        print(f"Error in update_user_data: {e}")

def get_user_rank(user_id):
    try:
        user = get_user_data(user_id)
        if user is None:
            return None, None, None
        
        user_coins = user['coins']
        higher_ranked_users = users_collection.count_documents({'coins': {'$gt': user_coins}})
        total_users = users_collection.count_documents({})

        rank = higher_ranked_users + 1
        next_user = users_collection.find_one({'coins': {'$gt': user_coins}}, sort=[('coins', 1)])
        coins_to_next_rank = next_user['coins'] - user_coins if next_user else None

        return rank, total_users, coins_to_next_rank
    except Exception as e:
        print(f"Error in get_user_rank: {e}")
        return None, None, None

def fetch_new_character():
    try:
        characters = list(characters_collection.find())
        return random.choice(characters) if characters else None
    except Exception as e:
        print(f"Error in fetch_new_character: {e}")
        return None

def add_character(image_url, character_name, rarity):
    try:
        character_id = characters_collection.count_documents({}) + 1
        character = {
            'id': character_id,
            'image_url': image_url,
            'character_name': character_name,
            'rarity': rarity
        }
        characters_collection.insert_one(character)
        return character
    except Exception as e:
        print(f"Error in add_character: {e}")
        return None

def delete_character(character_id):
    try:
        return characters_collection.delete_one({'id': character_id})
    except Exception as e:
        print(f"Error in delete_character: {e}")
        return None

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

# Command Handlers

# Welcome Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        user_id = message.from_user.id
        user = get_user_data(user_id)
        if not user['profile']:
            profile_name = message.from_user.full_name
            update_user_data(user_id, {'profile': profile_name})

        welcome_message = """
<b>🝮︎︎︎ Welcome to Pʜɪʟᴏ 🝮︎︎︎ Gᴀᴍᴇ 🝮︎︎︎</b>

🎮 Ready to dive into the world of anime characters? Let’s start collecting and guessing!

🝮︎︎︎ Use the commands below to explore all the features!
"""
        markup = InlineKeyboardMarkup()
        developer_button = InlineKeyboardButton(text="Developer - @TechPiro", url="https://t.me/TechPiro")
        markup.add(developer_button)

        bot.send_message(message.chat.id, welcome_message, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        print(f"Error in send_welcome: {e}")

# Help Command
@bot.message_handler(commands=['help'])
def show_help(message):
    try:
        help_message = """
<b>📜 🝮︎︎︎ Available Commands 🝮︎︎︎ 📜</b>

🎮 <b>Character Commands:</b>
/bonus - Claim your daily bonus 🝮︎︎︎
/inventory - View your character inventory 🝮︎︎︎
/gift - Gift coins to another user by tagging them 🝮︎︎︎
/profile - Show your personal stats (rank, coins, guesses, etc.) 🝮︎︎︎

🏆 <b>Leaderboards:</b>
/leaderboard - Show the top 10 users by coins 🝮︎︎︎
/topcoins - Show the top 10 users by coins earned today 🝮︎︎︎
/topgroups - Show the top 10 most active groups by messages 🝮︎︎︎

📊 <b>Bot Stats:</b>
/stats - Show the bot's stats (total users, characters, groups) 🝮︎︎︎

ℹ️ <b>Miscellaneous:</b>
/upload - Upload a new character (Sudo only) 🝮︎︎︎
/delete - Delete a character by ID (Sudo only) 🝮︎︎︎
/help - Show this help message 🝮︎︎︎

🝮︎︎︎ Have fun and start collecting! 🝮︎︎︎
"""
        bot.reply_to(message, help_message, parse_mode='HTML')
    except Exception as e:
        print(f"Error in show_help: {e}")

# Bonus Command
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    try:
        user_id = message.from_user.id
        user = get_user_data(user_id)
        last_bonus_time = user.get('last_bonus')

        if last_bonus_time:
            last_bonus = datetime.strptime(last_bonus_time, '%Y-%m-%d %H:%M:%S.%f')
        else:
            last_bonus = None

        now = datetime.utcnow()

        if last_bonus and now - last_bonus < BONUS_INTERVAL:
            remaining_time = BONUS_INTERVAL - (now - last_bonus)
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            bot.reply_to(message, f"🕑 You have already claimed your bonus. Please try again in {hours} hours and {minutes} minutes.")
        else:
            new_coins = user['coins'] + BONUS_COINS
            update_user_data(user_id, {'coins': new_coins, 'last_bonus': now.strftime('%Y-%m-%d %H:%M:%S.%f')})
            bot.reply_to(message, f"🎁 You claimed your daily bonus of {BONUS_COINS} coins! 🝮︎︎︎")
    except Exception as e:
        print(f"Error in claim_bonus: {e}")

# Add the remaining handlers here and ensure they follow the same structure.

# Start polling the bot
try:
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f"Error in bot polling: {e}")
