import os
import random
import logging
from datetime import datetime
from pymongo import MongoClient, errors
from telebot import TeleBot
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Load environment variables from .env file
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))
BONUS_COINS = int(os.getenv("BONUS_COINS", "10"))
STREAK_BONUS_COINS = int(os.getenv("STREAK_BONUS_COINS", "5"))
XP_PER_GUESS = 10
XP_THRESHOLD = 100
TOP_LEADERBOARD_LIMIT = int(os.getenv("TOP_LEADERBOARD_LIMIT", "10"))

# Initialize bot and MongoDB
bot = TeleBot(API_TOKEN)

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['philo_game']
    users_collection = db['users']
    characters_collection = db['characters']
    sudo_users_collection = db['sudo_users']
    chats_collection = db['chats']
    logging.info("✅ Connected to MongoDB successfully.")
except errors.ServerSelectionTimeoutError as err:
    logging.error(f"❌ Could not connect to MongoDB: {err}")
    exit()

# Utility Functions
def get_user_data(user_id, first_name="", last_name=""):
    """Fetches or creates user data."""
    try:
        return users_collection.find_one_and_update(
            {'user_id': user_id},
            {'$setOnInsert': {
                'user_id': user_id,
                'first_name': first_name,
                'last_name': last_name,
                'coins': 0,
                'correct_guesses': 0,
                'xp': 0,
                'level': 1,
                'inventory': [],
                'last_bonus': None,
                'streak': 0,
                'profile_name': f"{first_name} {last_name}".strip()
            }},
            upsert=True,
            return_document=True
        )
    except Exception as e:
        logging.error(f"Error retrieving or creating user data: {e}")
        return None

def update_user_data(user_id, update_data):
    """Updates user data in the database."""
    try:
        users_collection.update_one({'user_id': user_id}, {'$set': update_data})
    except errors.PyMongoError as e:
        logging.error(f"Failed to update user data: {e}")

def fetch_new_character(group=None):
    """Fetches a random character, optionally filtered by group."""
    try:
        query = {}
        if group:
            query['group'] = group  # Assuming characters have a 'group' field
        characters = list(characters_collection.find(query))
        if characters:
            return random.choice(characters)
        else:
            logging.info(f"No characters found for group: {group}")
            return None
    except errors.PyMongoError as e:
        logging.error(f"Error fetching character: {e}")
        return None

def calculate_level(xp):
    """Calculates the level based on XP."""
    return (xp // XP_THRESHOLD) + 1

def is_sudo_user(user_id):
    """Checks if the user is a sudo user."""
    try:
        return user_id == BOT_OWNER_ID or sudo_users_collection.find_one({"user_id": user_id}) is not None
    except errors.PyMongoError as e:
        logging.error(f"Error checking sudo user: {e}")
        return False

# Bot Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handles the /start command."""
    try:
        user_id = message.from_user.id
        first_name = message.from_user.first_name or "Unknown"
        last_name = message.from_user.last_name or ""
        chat_id = message.chat.id

        if message.chat.type in ['group', 'supergroup']:
            chats_collection.update_one({'chat_id': chat_id}, {'$set': {'chat_id': chat_id}}, upsert=True)

        user = get_user_data(user_id, first_name, last_name)
        user_name = f"{first_name} {last_name}".strip()
        bot.reply_to(
            message,
            f"❖ Welcome to *Philo Game*, {user_name}!\n"
            f"❖ Use `/help` to see available commands.",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        logging.error(f"Error in /start command: {e}")

@bot.message_handler(commands=['help'])
def show_help(message):
    """Displays help information."""
    help_message = """
<b>❖ Available Commands:</b>
❖ /start - Welcome message and profile creation
❖ /bonus - Claim daily bonus coins
❖ /profile - View your stats and game progress
❖ /levels - Show top players by coins
❖ /stats - Show bot statistics (Owner only)
❖ /upload - Upload a new character (Admin and Sudo only)
❖ /addsudo - Add a sudo user (Owner only)
❖ /broadcast - Broadcast a message to all chats (Owner only)
❖ /gift - Gift coins to another player by username or @mention
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

@bot.message_handler(commands=['levels'])
def show_levels(message):
    """Displays the leaderboard."""
    try:
        top_users = users_collection.find().sort("coins", -1).limit(TOP_LEADERBOARD_LIMIT)
        leaderboard = "<b>❖ 🏆 Top Players by Coins 🏆 ❖</b>\n\n"
        
        for i, user in enumerate(top_users, 1):
            profile_name = user.get('profile_name', 'Unknown')
            coins = user.get('coins', 0)
            leaderboard += f"❖ <b>{i}. {profile_name}</b> - {coins} coins\n"

        bot.reply_to(message, leaderboard, parse_mode='HTML')
    except errors.PyMongoError as e:
        logging.error(f"Error fetching leaderboard: {e}")
        bot.reply_to(message, "❖ ❌ Failed to fetch leaderboard. Please try again later.")
    except Exception as e:
        logging.error(f"Unexpected error in /levels command: {e}")
        bot.reply_to(message, "❖ ❌ An unexpected error occurred. Please try again later.")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    """Displays the user's profile."""
    try:
        user_id = message.from_user.id
        user = get_user_data(user_id)

        if user:
            xp = user.get('xp', 0)
            level = calculate_level(xp)

            if level != user.get('level', 1):
                update_user_data(user_id, {'level': level})

            profile_name = user.get('profile_name', 'Unknown')
            coins = user.get('coins', 0)
            correct_guesses = user.get('correct_guesses', 0)
            streak = user.get('streak', 0)
            inventory = user.get('inventory', [])
            last_bonus = user.get('last_bonus', None)

            last_bonus_text = (
                f"{datetime.fromtimestamp(last_bonus).strftime('%Y-%m-%d %H:%M:%S')}"
                if last_bonus else "❖ None"
            )
            inventory_text = ", ".join(inventory) if inventory else "❖ Empty"

            profile_text = (
                f"❖ <b>👤 Profile of {profile_name}</b>\n\n"
                f"❖ 💰 <b>Coins:</b> {coins}\n"
                f"❖ 🎯 <b>Correct Guesses:</b> {correct_guesses}\n"
                f"❖ 🔥 <b>Streak:</b> {streak} days\n"
                f"❖ 🌟 <b>Level:</b> {level}\n"
                f"❖ 📈 <b>XP:</b> {xp} / {XP_THRESHOLD} for next level\n"
                f"❖ 🎒 <b>Inventory:</b> {inventory_text}\n"
                f"❖ ⏰ <b>Last Bonus Claimed:</b> {last_bonus_text}\n"
            )
            bot.reply_to(message, profile_text, parse_mode='HTML')
        else:
            bot.reply_to(message, "❖ ❌ Could not retrieve your profile. Please try again later.")
    except Exception as e:
        logging.error(f"Error in /profile command: {e}")
        bot.reply_to(message, "❖ ❌ An error occurred while fetching your profile.")

# Start bot polling
try:
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
except Exception as e:
    logging.error(f"Error during bot polling: {e}")
