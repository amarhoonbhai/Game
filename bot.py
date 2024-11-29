import os
import random
import logging
import time
from datetime import datetime, timedelta
from pymongo import MongoClient, errors
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
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

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))
RARITY_LEVELS = ["Common", "Rare", "Epic", "Legendary"]
RARITY_POINTS = {"Common": 10, "Rare": 25, "Epic": 50, "Legendary": 100}

# Validate environment variables
if not API_TOKEN or not MONGO_URI:
    logging.error("❌ Missing required environment variables. Please check .env file.")
    exit()

# Initialize bot and MongoDB
bot = TeleBot(API_TOKEN)
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['philo_game']
    users_collection = db['users']
    characters_collection = db['characters']
    sudo_users_collection = db['sudo_users']
    message_counts_collection = db['message_counts']
    chats_collection = db['chats']
    active_games = {}  # Tracks active games per chat
    logging.info("✅ Connected to MongoDB successfully.")
except errors.ServerSelectionTimeoutError as err:
    logging.error(f"❌ Could not connect to MongoDB: {err}")
    exit()

# Utility Functions
def calculate_level(xp):
    """Calculates the level based on XP."""
    max_level = 1000
    level = (xp // 100) + 1
    return min(level, max_level)

def get_title(level):
    """Assigns a title based on the level."""
    if level == 1000:
        return "Overpowered"
    elif level <= 3:
        return "Novice Guesser"
    elif level <= 6:
        return "Intermediate Guesser"
    elif level <= 9:
        return "Expert Guesser"
    else:
        return "Master Guesser"

def is_sudo_user(user_id):
    """Checks if the user is a sudo user."""
    try:
        return user_id == BOT_OWNER_ID or sudo_users_collection.find_one({"user_id": user_id}) is not None
    except errors.PyMongoError as e:
        logging.error(f"Error checking sudo user: {e}")
        return False

def auto_assign_rarity():
    """Automatically assigns a rarity level."""
    probabilities = [0.6, 0.25, 0.1, 0.05]  # Common, Rare, Epic, Legendary
    return random.choices(RARITY_LEVELS, probabilities)[0]

def increment_message_count(chat_id):
    """Increments the message count for a chat and checks the threshold."""
    try:
        result = message_counts_collection.find_one_and_update(
            {'chat_id': chat_id},
            {'$inc': {'message_count': 1}},
            upsert=True,
            return_document=True
        )
        if result and result.get('message_count', 0) >= 5:
            message_counts_collection.update_one({'chat_id': chat_id}, {'$set': {'message_count': 0}})
            return True
        return False
    except Exception as e:
        logging.error(f"Error incrementing message count: {e}")
        return False

def start_new_character_game(chat_id):
    """Starts a new game with a random character."""
    try:
        character = characters_collection.aggregate([{'$sample': {'size': 1}}]).next()
        active_games[chat_id] = character
        caption = (
            f"🎉 A new character appears! 🎉\n\n"
            f"👤 <b>Name:</b> ???\n"
            f"✨ <b>Rarity:</b> {character['rarity']}\n"
            f"📸 Guess the character's name!"
        )
        bot.send_photo(chat_id, character['image_url'], caption=caption, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error starting new character game: {e}")

def reward_user(user_id, chat_id, character):
    """Rewards the user for guessing the character's name and starts a new game."""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return

        points = RARITY_POINTS.get(character['rarity'], 0)
        last_played = user.get('last_played')
        streak = user.get('streak', 0)

        if last_played and (datetime.utcnow() - last_played).days <= 1:
            streak += 1
        else:
            streak = 1

        users_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'coins': points, 'correct_guesses': 1, 'xp': points},
                '$set': {'last_played': datetime.utcnow(), 'streak': streak}
            }
        )

        bot.send_message(
            chat_id,
            f"🎉 <b>Correct!</b> The character was <b>{character['name']}</b>.\n"
            f"✨ You've earned <b>{points} coins</b>!\n"
            f"🔥 Current Streak: <b>{streak} days</b>\n"
            f"Rarity: {character['rarity']}",
            parse_mode='HTML'
        )

        start_new_character_game(chat_id)

    except Exception as e:
        logging.error(f"Error rewarding user: {e}")

def calculate_bonus(streak):
    """Calculates bonus coins based on the current streak."""
    return 10 + (streak * 5)

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handles the /start command and welcomes the user."""
    try:
        user_id = message.from_user.id
        first_name = message.from_user.first_name or "Unknown"
        chat_id = message.chat.id

        users_collection.find_one_and_update(
            {'user_id': user_id},
            {'$setOnInsert': {
                'user_id': user_id,
                'first_name': first_name,
                'coins': 0,
                'correct_guesses': 0,
                'xp': 0,
                'level': 1,
                'streak': 0,
                'last_bonus': None,
                'joined_at': datetime.utcnow()
            }},
            upsert=True
        )

        welcome_message = (
            f"🎉 <b>Welcome to Philo Guesser, {first_name}!</b> 🎉\n\n"
            f"🕵️‍♂️ <b>Your Mission:</b> Guess the names of philosophers and famous personalities.\n\n"
            f"✨ <b>How to Play:</b>\n"
            f"1️⃣ Characters will appear in the chat with a hint and an image.\n"
            f"2️⃣ Type their name to guess — no commands needed!\n"
            f"3️⃣ Earn points based on the character's rarity.\n\n"
            f"🏆 <b>Rarities & Points:</b>\n"
            f"• Common: 10 points\n"
            f"• Rare: 25 points\n"
            f"• Epic: 50 points\n"
            f"• Legendary: 100 points\n\n"
            f"Use <b>/help</b> to see all available commands. Good luck!"
        )

        bot.send_message(chat_id, welcome_message, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error in /start command: {e}")
        bot.reply_to(message, "❌ An error occurred while processing your request.")

@bot.message_handler(commands=['help'])
def show_help(message):
    """Displays help information with a developer inline button."""
    try:
        help_message = (
            f"🛠️ <b>Philo Guesser Help Menu</b> 🛠️\n\n"
            f"📌 <b>Commands:</b>\n"
            f"• /start - Start your journey\n"
            f"• /help - Display this help message\n"
            f"• /levels - View the leaderboard\n"
            f"• /profile - View your profile\n"
            f"• /bonus - Claim your daily bonus\n"
            f"✨ Guess names directly in chat to earn points!"
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/techpiro"))

        bot.send_message(message.chat.id, help_message, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        logging.error(f"Error in /help command: {e}")
        bot.reply_to(message, "❌ An error occurred while displaying the help menu.")

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    """Allows users to claim a daily bonus."""
    try:
        user = users_collection.find_one({'user_id': message.from_user.id})
        if not user:
            bot.reply_to(message, "❌ You must use /start first!")
            return
        
        now = datetime.utcnow()
        last_bonus = user.get('last_bonus')

        if last_bonus and now - last_bonus < timedelta(hours=24):
            bot.reply_to(message, "⏳ You have already claimed your bonus today. Try again later!")
            return

        bonus = 50  # Fixed bonus amount
        users_collection.update_one(
            {'user_id': user['user_id']},
            {'$inc': {'coins': bonus}, '$set': {'last_bonus': now}}
        )

        bot.reply_to(message, f"🎉 You've claimed your daily bonus of {bonus} coins!")
    except Exception as e:
        logging.error(f"Error in /bonus command: {e}")
        bot.reply_to(message, "❌ Could not process your bonus.")

@bot.message_handler(commands=['levels'])
def show_leaderboard(message):
    """Displays the leaderboard of top users."""
    try:
        top_users = users_collection.find().sort("coins", -1).limit(10)
        leaderboard = "\n".join(
            [f"{i+1}. {user['first_name']} - {user['coins']} coins" for i, user in enumerate(top_users)]
        )
        bot.send_message(message.chat.id, f"🏆 <b>Leaderboard</b> 🏆\n\n{leaderboard}", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error in /levels command: {e}")
        bot.reply_to(message, "❌ Could not retrieve leaderboard.")

@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def handle_message(message):
    """Handles guessing and character appearance logic."""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        user_text = message.text.strip().lower()

        if chat_id in active_games:
            character = active_games[chat_id]
            if user_text == character['name'].lower():
                reward_user(user_id, chat_id, character)
                del active_games[chat_id]
            else:
                bot.reply_to(message, "❌ Incorrect! Try again.")
        else:
            if increment_message_count(chat_id):
                start_new_character_game(chat_id)
    except Exception as e:
        logging.error(f"Error handling message: {e}")

# Main polling loop with retries
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logging.error(f"Error during bot polling: {e}")
        time.sleep(5)  # Wait before retrying
