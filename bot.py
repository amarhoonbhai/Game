import telebot
import random
import json
from collections import defaultdict
from datetime import datetime, timedelta
import os

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7825167784:AAGPxv8kCN-jRN1md4uAaw3P--Lvw71gmtg"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

bot = telebot.TeleBot(API_TOKEN)

# File paths for storing data
USER_DATA_FILE = 'user_data.json'
CHARACTER_DATA_FILE = 'characters.json'

# In-memory store for game data (loaded from JSON)
user_data = {
    "user_coins": defaultdict(int),
    "user_profiles": {},
    "user_correct_guesses": defaultdict(int),
    "user_inventory": defaultdict(list),
    "user_last_bonus": {},
    "user_streak": defaultdict(int)
}

characters = []  # List of uploaded characters (with ID)
current_character = None
global_message_count = 0  # Global counter for messages in all chats

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
character_id_counter = 1  # Counter for character IDs
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character

# Helper Functions to load and save data
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            data = json.load(f)
            user_data["user_coins"].update(data.get("user_coins", {}))
            user_data["user_profiles"].update(data.get("user_profiles", {}))
            user_data["user_correct_guesses"].update(data.get("user_correct_guesses", {}))
            user_data["user_inventory"].update(data.get("user_inventory", {}))
            user_data["user_last_bonus"].update(data.get("user_last_bonus", {}))
            user_data["user_streak"].update(data.get("user_streak", {}))

def save_user_data():
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(user_data, f, indent=4)

def load_character_data():
    global character_id_counter
    if os.path.exists(CHARACTER_DATA_FILE):
        with open(CHARACTER_DATA_FILE, 'r') as f:
            data = json.load(f)
            characters.extend(data)
            if characters:
                character_id_counter = max(c['id'] for c in characters) + 1  # Set the next ID to the max existing ID + 1

def save_character_data():
    with open(CHARACTER_DATA_FILE, 'w') as f:
        json.dump(characters, f, indent=4)

# Function to add coins and save user data
def add_coins(user_id, coins):
    user_data["user_coins"][user_id] += coins
    save_user_data()

# Function to display rarity randomly
def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

# Command to display welcome message and help commands
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_data["user_profiles"][user_id] = message.from_user.username or message.from_user.first_name
    save_user_data()

    welcome_message = f"""
    ✨ *Welcome to Philo Grabber!* ✨

    🎮 _Let the Anime Character Guessing Game Begin!_ 🎮

    👑 *Owner*: [TechPiro](https://t.me/TechPiro)
    
    💡 Type /help to see the available commands.

    Have fun collecting and guessing anime characters! 🤩
    """
    bot.reply_to(message, welcome_message, parse_mode='Markdown')

    # Automatically show /help message after welcome
    show_help(message)

# Command to display available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
    ━━━━━━━━━━━━━━━━━━━━━━
    🤖 *Available Commands*:

    - `/bonus` - Claim your daily reward of 50,000 coins
    - `/profile` - View your profile with stats and achievements
    - `/inventory` - View your collected characters
    - `/leaderboard` - Show the leaderboard
    - `/upload <image_url> <character_name>` - Upload a new character (Owner only)
    - `/delete <character_id>` - Delete a character (Owner only)
    - `/stats` - Show bot statistics (Owner only)
    ━━━━━━━━━━━━━━━━━━━━━━
    """
    bot.reply_to(message, help_message, parse_mode='Markdown')

# Command to display user profile
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    coins = user_data["user_coins"][user_id]
    correct_guesses = user_data["user_correct_guesses"][user_id]
    inventory_count = len(user_data["user_inventory"][user_id])
    streak = user_data["user_streak"][user_id]

    profile_message = (
        f"👤 *Profile*\n\n"
        f"💰 Coins: {coins}\n"
        f"✅ Correct Guesses: {correct_guesses}\n"
        f"🔥 Streak: {streak}\n"
        f"📦 Inventory: {inventory_count} characters"
    )
    bot.reply_to(message, profile_message, parse_mode='Markdown')

# Command to display inventory
@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    inventory = user_data["user_inventory"][user_id]

    if not inventory:
        bot.reply_to(message, "🎒 Your inventory is empty. Start guessing characters to collect them!")
    else:
        inventory_message = f"🎒 *Your Character Collection*:\n"
        inventory_count = {}
        for character in inventory:
            key = (character['character_name'], character['rarity'])
            inventory_count[key] = inventory_count.get(key, 0) + 1

        for i, ((character_name, rarity), count) in enumerate(inventory_count.items(), 1):
            inventory_message += f"{i}. {character_name} ({rarity}) x{count if count > 1 else ''}\n"
        
        bot.reply_to(message, inventory_message, parse_mode='Markdown')

# Start the bot polling
bot.infinity_polling()
