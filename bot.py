import telebot
import random
import json
from collections import defaultdict
from datetime import datetime, timedelta
import os

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7825167784:AAES3h0yneJOOjBP-dvDVcEeY2HqAlDq-UI"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# List of sudo users (user IDs)
SUDO_USERS = [7222795580, 1234567890]  # Add user IDs of sudo users here

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

# Ensure user data gets saved after each modification
def add_coins(user_id, coins):
    user_data["user_coins"][user_id] += coins
    save_user_data()

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    if characters:
        return random.choice(characters)
    return None

def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {current_character['rarity']}\n"
        )
        bot.send_photo(chat_id, current_character['image_url'], caption=caption)

def find_character_by_id(char_id):
    for character in characters:
        if character['id'] == char_id:
            return character
    return None

# Function to check if the user is the bot owner or a sudo user
def is_owner_or_sudo(user_id):
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    # Capture the user's username, and if not available, fallback to first_name
    user_data["user_profiles"][user_id] = message.from_user.username or message.from_user.first_name
    save_user_data()
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Type /help for commands.")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available Commands:
/bonus - Claim your daily reward (50,000 coins every 24 hours)
/profile - View your profile
/inventory - View your collected characters
/leaderboard - Show the top 10 leaderboard
/upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only)
/delete <character_id> - Delete a character (Owner only)
/stats - Show bot statistics (Owner only)
"""
    bot.reply_to(message, help_message)

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    now = datetime.now()

    # Check if the user can claim the bonus
    if user_id in user_data["user_last_bonus"] and now - datetime.fromisoformat(user_data["user_last_bonus"][user_id]) < BONUS_INTERVAL:
        next_claim = datetime.fromisoformat(user_data["user_last_bonus"][user_id]) + BONUS_INTERVAL
        remaining_time = next_claim - now
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"You can claim your next bonus in {hours_left} hours and {minutes_left} minutes.")
    else:
        add_coins(user_id, BONUS_COINS)
        user_data["user_last_bonus"][user_id] = now.isoformat()  # Save ISO format datetime
        save_user_data()
        bot.reply_to(message, f"🎉 You have received {BONUS_COINS} coins!")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    global character_id_counter

    # Only the owner and sudo users can upload characters
    if not is_owner_or_sudo(message.from_user.id):
        bot.reply_to(message, "You do not have permission to upload characters.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "Format: /upload <image_url> <character_name>")
        return

    rarity = assign_rarity()
    character = {'id': character_id_counter, 'image_url': image_url, 'character_name': character_name, 'rarity': rarity}
    characters.append(character)
    save_character_data()  # Save the new character to the file
    bot.send_message(CHANNEL_ID, f"New character uploaded: {character_name} (ID: {character_id_counter}, {RARITY_LEVELS[rarity]} {rarity})")
    bot.reply_to(message, f"✅ Character '{character_name}' uploaded successfully with ID {character_id_counter}!")
    character_id_counter += 1

@bot.message_handler(commands=['delete'])
def delete_character(message):
    # Only the owner (BOT_OWNER_ID) can delete characters
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "You do not have permission to delete characters.")
        return

    try:
        _, char_id_str = message.text.split(maxsplit=1)
        char_id = int(char_id_str)
    except (ValueError, IndexError):
        bot.reply_to(message, "Format: /delete <character_id>")
        return

    character = find_character_by_id(char_id)
    if character:
        characters.remove(character)
        save_character_data()  # Save the updated character list
        bot.reply_to(message, f"✅ Character with ID {char_id} ('{character['character_name']}') has been deleted.")
    else:
        bot.reply_to(message, f"❌ Character with ID {char_id} not found.")

# Other commands like profile, inventory, leaderboard, etc. remain the same

# Load user and character data at startup
load_user_data()
load_character_data()

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
