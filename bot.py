import os
import telebot
import random
import threading
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve values from .env
API_TOKEN = os.getenv('TELEGRAM_BOT_API_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))  # Ensure this is an integer

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# MongoDB Setup
client = MongoClient(MONGO_URI)
db = client['anime_game']  # Database name
characters_collection = db['characters']  # Collection for characters
users_collection = db['users']  # Collection for users
redeem_collection = db['redeem_codes']  # Collection for redeem codes

# Define bot owner and sudo users
bot_owner_id = "7222795580" # Replace with your Telegram user ID
sudo_users = "7222795580" "6180999156"   # Add other sudo user IDs if necessary

# Rarity levels
RARITY_LEVELS = {
    'elite': '⚡',
    'epic': '💫',
    'legendary': '🥂',
    'mythical': '🔮'
}

# Current character being displayed (we'll store its image URL, name, and rarity)
current_character = {
    "image_url": None,
    "name": None,
    "rarity": None
}

# Track users and groups
unique_users = set()
unique_groups = set()

# Generate a redeem code every hour
current_redeem_code = None
redeem_code_expiry = None

# Track users and groups for statistics
def track_user_and_group(message):
    if message.chat.type == 'private':
        unique_users.add(message.from_user.id)  # Track unique user
    elif message.chat.type in ['group', 'supergroup']:
        unique_groups.add(message.chat.id)  # Track unique group

# Get player data from MongoDB
def get_player_data(user_id, username):
    player = users_collection.find_one({"user_id": user_id})
    if not player:
        player = {
            "user_id": user_id,
            "username": username,
            "coins": 0,
            "correct_guesses": 0,
            "streak": 0,
            "last_daily": None,
            "last_redeem": None
        }
        users_collection.insert_one(player)
    return player

# Update player data in MongoDB
def update_player_data(user_id, coins=None, correct_guesses=None, streak=None, last_daily=None, last_redeem=None):
    player = get_player_data(user_id, "")
    updated_data = {
        "coins": coins if coins is not None else player["coins"],
        "correct_guesses": correct_guesses if correct_guesses is not None else player["correct_guesses"],
        "streak": streak if streak is not None else player["streak"],
        "last_daily": last_daily if last_daily is not None else player["last_daily"],
        "last_redeem": last_redeem if last_redeem is not None else player["last_redeem"]
    }
    users_collection.update_one({"user_id": user_id}, {"$set": updated_data})

# Store uploaded character in MongoDB
def store_character(image_url, name, rarity):
    character = {"image_url": image_url, "name": name.lower(), "rarity": rarity}
    characters_collection.insert_one(character)

# Fetch a random character from MongoDB
def get_random_character():
    characters = list(characters_collection.find())
    if not characters:
        return None
    return random.choice(characters)

# Upload Command - For bot owner and sudo users to upload characters via image URL
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not (message.from_user.id == bot_owner_id or message.from_user.id in sudo_users):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    # Format should be: /upload <image_url> <name> <rarity>
    command_parts = message.text.split()
    if len(command_parts) == 4:
        image_url = command_parts[1]
        name = command_parts[2].lower()
        rarity = command_parts[3].lower()

        if rarity not in RARITY_LEVELS:
            bot.reply_to(message, "❌ Invalid rarity! Use: Elite ⚡, Epic 💫, Legendary 🥂, Mythical 🔮.")
            return

        # Store character in MongoDB
        store_character(image_url, name, rarity)

        bot.reply_to(message, f"✅ Character '{name.capitalize()}' uploaded successfully with rarity: {rarity.capitalize()}")

        # Send the character image and details to the log channel
        bot.send_photo(LOG_CHANNEL_ID, image_url, caption=f"📥 A new character was uploaded:\nName: {name.capitalize()}\nRarity: {rarity.capitalize()}")
    else:
        bot.reply_to(message, "❌ Incorrect format. Use: /upload <image_url> <name> <rarity>")

# Start Command - Starts the bot and shows a welcome message
@bot.message_handler(commands=['start'])
def send_welcome(message):
    track_user_and_group(message)
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Use /help for available commands.")

# Help Command - Shows all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    track_user_and_group(message)
    help_message = """
Available commands:
/start - Start the bot and get a welcome message
/upload <image_url> <name> <rarity> - (Sudo/Owner only) Upload a character by image URL, name, and rarity (Elite ⚡, Epic 💫, Legendary 🥂, Mythical 🔮)
/redeem - Redeem coins (available every hour)
/leaderboard - Show the leaderboard with top players
/daily_reward - Claim your daily coins reward
/redeem_code - Show current redeem code
/help - Show this help message
"""
    bot.reply_to(message, help_message)

# More bot functionalities here...

# Run the bot
bot.infinity_polling()
