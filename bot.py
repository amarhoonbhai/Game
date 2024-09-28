import telebot
import random
import logging
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAGDwqtzms4ZaBwwWMFp4RRMTPdjfd2wwH0"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
client = MongoClient(MONGO_URI)
db = client['philo_grabber']  # Database name
users_collection = db['users']  # Collection for user data
characters_collection = db['characters']  # Collection for character data
groups_collection = db['groups']  # Collection for group data (tracking messages)

# List of sudo users (user IDs)
SUDO_USERS = [7222795580, 6180999156]  # Add user IDs of sudo users here

bot = telebot.TeleBot(API_TOKEN)

# Logging Setup
logging.basicConfig(filename='bot_activity.log', level=logging.INFO, format='%(asctime)s - %(message)s')
logging.info("Bot started.")

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
current_character = None
global_message_count = 0  # Global counter for messages in all chats


# Helper Functions
def get_user_data(user_id):
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
        logging.info(f"New user created: {user_id}")
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_character_data():
    return list(characters_collection.find())

def add_character(image_url, character_name, rarity):
    character_id = characters_collection.count_documents({}) + 1
    character = {
        'id': character_id,
        'image_url': image_url,
        'character_name': character_name,
        'rarity': rarity
    }
    characters_collection.insert_one(character)
    logging.info(f"Character added: {character_name} (ID: {character_id}, Rarity: {rarity})")
    return character

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    characters = get_character_data()
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
        logging.info(f"Character sent to chat {chat_id}: {current_character['character_name']} (Rarity: {rarity})")

def is_owner_or_sudo(user_id):
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS


# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.username or message.from_user.first_name
        update_user_data(user_id, {'profile': profile_name})
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Type /help for commands.")
    logging.info(f"User {user_id} started the bot.")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available Commands:
/bonus - Claim your daily reward (50,000 coins every 24 hours)
/profile - View your profile
/inventory - View your collected characters (grouped by rarity)
/leaderboard - Show the top 10 leaderboard
/topgroups - Show the top 5 groups with most messages
/topusers - Show the top 5 users with most guesses
/upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only)
/delete <character_id> - Delete a character (Owner only)
/stats - Show bot statistics (Owner only)
"""
    bot.reply_to(message, help_message)
    logging.info(f"User {message.from_user.id} requested /help")

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    now = datetime.now()

    if user['last_bonus'] and now - datetime.fromisoformat(user['last_bonus']) < BONUS_INTERVAL:
        next_claim = datetime.fromisoformat(user['last_bonus']) + BONUS_INTERVAL
        remaining_time = next_claim - now
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"You can claim your next bonus in {hours_left} hours and {minutes_left} minutes.")
    else:
        new_coins = user['coins'] + BONUS_COINS
        update_user_data(user_id, {'coins': new_coins, 'last_bonus': now.isoformat()})
        bot.reply_to(message, f"🎉 You have received {BONUS_COINS} coins!")
        logging.info(f"User {user_id} claimed bonus: {BONUS_COINS} coins.")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_owner_or_sudo(message.from_user.id):
        bot.reply_to(message, "You do not have permission to upload characters.")
        logging.warning(f"Unauthorized upload attempt by user {message.from_user.id}")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "Format: /upload <image_url> <character_name>")
        return

    rarity = assign_rarity()
    character = add_character(image_url, character_name, rarity)
    bot.send_message(CHANNEL_ID, f"New character uploaded: {character_name} (ID: {character['id']}, {RARITY_LEVELS[rarity]} {rarity})")
    bot.reply_to(message, f"✅ Character '{character_name}' uploaded successfully with ID {character['id']}!")

@bot.message_handler(commands=['delete'])
def delete_character(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "You do not have permission to delete characters.")
        logging.warning(f"Unauthorized delete attempt by user {message.from_user.id}")
        return

    try:
        _, char_id_str = message.text.split(maxsplit=1)
        char_id = int(char_id_str)
    except (ValueError, IndexError):
        bot.reply_to(message, "Format: /delete <character_id>")
        return

    character = characters_collection.find_one({'id': char_id})
    if character:
        characters_collection.delete_one({'id': char_id})
        bot.reply_to(message, f"✅ Character with ID {char_id} ('{character['character_name']}') has been deleted.")
        logging.info(f"Character deleted: {char_id}")
    else:
        bot.reply_to(message, f"❌ Character with ID {char_id} not found.")
        logging.warning(f"Character delete attempt failed, ID {char_id} not found.")

# The rest of the bot code remains the same...

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
