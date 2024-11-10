import os
import telebot
from pymongo import MongoClient, errors
from dotenv import load_dotenv
import random
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Load environment variables from .env file
load_dotenv()

# Configuration variables
API_TOKEN = os.getenv("API_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BONUS_COINS = int(os.getenv("BONUS_COINS", 5000))
BONUS_INTERVAL = timedelta(days=1)
COINS_PER_GUESS = 50
MESSAGE_THRESHOLD = 5
captions_for_correct_guesses = [
    "🎉 Brilliant guess!",
    "🎊 You've cracked it!",
    "🔥 Spot on! You nailed it!",
    "✨ Right answer, amazing!",
    "🎈 You guessed it perfectly!"
]

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client['philo_grabber']
users_collection = db['users']
characters_collection = db['characters']
sudo_users_collection = db['sudo_users']

# Initialize bot
bot = telebot.TeleBot(API_TOKEN)

# Helper Functions
def is_sudo_user(user_id):
    """Check if a user is a sudo user."""
    return sudo_users_collection.find_one({'user_id': user_id}) is not None

def get_user_data(user_id):
    """Retrieve or create user data."""
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        user = {
            'user_id': user_id,
            'coins': 0,
            'last_bonus': None,
            'correct_guesses': 0,
            'level': 1,
            'inventory': []
        }
        users_collection.insert_one(user)
    return user

def update_user_data(user_id, update_data):
    """Update user data."""
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def assign_rarity():
    """Assign rarity to a character."""
    rarities = ['Common', 'Rare', 'Epic', 'Legendary']
    weights = [60, 25, 10, 5]
    return random.choices(rarities, weights=weights, k=1)[0]

def fetch_new_character():
    """Fetch a random character."""
    characters = list(characters_collection.find())
    return random.choice(characters) if characters else None

# Commands
@bot.message_handler(commands=['addsudo'])
def add_sudo_user(message):
    """Add a sudo user."""
    if message.from_user.id == BOT_OWNER_ID:
        try:
            parts = message.text.split()
            if len(parts) != 2:
                bot.reply_to(message, "Usage: /addsudo <user_id>")
                return
            new_sudo_id = int(parts[1])
            if is_sudo_user(new_sudo_id):
                bot.reply_to(message, "This user is already a sudo user.")
            else:
                sudo_users_collection.insert_one({'user_id': new_sudo_id})
                bot.reply_to(message, f"✅ User {new_sudo_id} added as a sudo user.")
        except Exception as e:
            bot.reply_to(message, f"Error adding sudo user: {e}")
    else:
        bot.reply_to(message, "You don't have permission to use this command.")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    """Allow sudo users and bot owner to upload characters."""
    user_id = message.from_user.id
    if user_id == BOT_OWNER_ID or is_sudo_user(user_id):
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                bot.reply_to(message, "Usage: /upload <image_url> <character_name>")
                return
            image_url, character_name = parts[1], parts[2]
            rarity = assign_rarity()
            new_character = {
                'image_url': image_url,
                'character_name': character_name,
                'rarity': rarity
            }
            characters_collection.insert_one(new_character)
            bot.reply_to(message, f"Character '{character_name}' with rarity '{rarity}' uploaded successfully!")
        except Exception as e:
            bot.reply_to(message, f"Error uploading character: {e}")
    else:
        bot.reply_to(message, "You don't have permission to use this command.")

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    """Claim daily bonus coins."""
    user_id = message.from_user.id
    user = get_user_data(user_id)
    current_time = datetime.now()
    if user['last_bonus'] and current_time - user['last_bonus'] < BONUS_INTERVAL:
        bot.reply_to(message, "You've already claimed your bonus today!")
    else:
        new_coins = user['coins'] + BONUS_COINS
        update_user_data(user_id, {'coins': new_coins, 'last_bonus': current_time})
        bot.reply_to(message, f"🎁 You received your daily bonus of {BONUS_COINS} coins!")

@bot.message_handler(commands=['stats'])
def show_bot_stats(message):
    """Display bot statistics."""
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    total_sudo_users = sudo_users_collection.count_documents({})
    bot.reply_to(message, f"📊 Bot Stats:\nUsers: {total_users}\nCharacters: {total_characters}\nSudo Users: {total_sudo_users}")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    """Show user's profile with their coins, level, and correct guesses."""
    user_id = message.from_user.id
    user = get_user_data(user_id)
    bot.reply_to(message, f"👤 Profile:\nCoins: {user['coins']}\nLevel: {user['level']}\nCorrect Guesses: {user['correct_guesses']}")

@bot.message_handler(commands=['levels'])
def show_top_users(message):
    """Show top users by levels."""
    top_users = users_collection.find().sort('level', -1).limit(10)
    leaderboard = "\n".join([f"{i+1}. {user['user_id']} - Level {user['level']}" for i, user in enumerate(top_users)])
    bot.reply_to(message, f"🏆 Top Levels:\n{leaderboard}")

@bot.message_handler(commands=['help'])
def show_help(message):
    """Display help message with available commands."""
    help_text = (
        "📖 <b>Available Commands</b> 📖\n\n"
        "<b>User Commands:</b>\n"
        "/bonus - Claim your daily bonus 🎁\n"
        "/profile - View your profile 👤\n"
        "/stats - Show bot statistics 📊\n"
        "/levels - Show the top users by levels 🏆\n\n"
        "<b>Sudo Commands:</b>\n"
        "/upload <image_url> <character_name> - Upload a new character\n"
        "/addsudo <user_id> - Add a user as sudo"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

def send_character(chat_id):
    """Send a character to the chat for guessing."""
    character = fetch_new_character()
    if character:
        caption = f"🎉 Guess the Character!\nRarity: {character['rarity']}\nName: ???"
        bot.send_photo(chat_id, character['image_url'], caption=caption)
    else:
        bot.send_message(chat_id, "No characters available.")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all messages for correct guess detection and new character send."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip().lower() if message.text else ""

    character = fetch_new_character()
    if character and text == character['character_name'].strip().lower():
        user = get_user_data(user_id)
        new_coins = user['coins'] + COINS_PER_GUESS
        update_user_data(user_id, {'coins': new_coins, 'correct_guesses': user['correct_guesses'] + 1})
        caption = random.choice(captions_for_correct_guesses)
        bot.reply_to(message, f"{caption} You've earned {COINS_PER_GUESS} coins.")
        send_character(chat_id)

# Start polling
bot.infinity_polling(timeout=60, long_polling_timeout=60)
