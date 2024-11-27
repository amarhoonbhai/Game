import os
import random
import logging
from datetime import datetime
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
    """Rewards the user for guessing the character's name."""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return

        points = RARITY_POINTS.get(character['rarity'], 0)
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'coins': points, 'correct_guesses': 1, 'xp': points},
                '$set': {'last_played': datetime.utcnow()}
            }
        )

        bot.send_message(
            chat_id,
            f"🎉 <b>Correct!</b> The character was <b>{character['name']}</b>.\n"
            f"✨ You've earned <b>{points} points</b>!\n"
            f"Rarity: {character['rarity']}",
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Error rewarding user: {e}")

# Bot Commands
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
                'joined_at': datetime.utcnow()
            }},
            upsert=True
        )

        welcome_message = (
            f"🎉 <b>Welcome to Philo Guesser, {first_name}!</b> 🎉\n\n"
            f"🕵️‍♂️ <b>Your Mission:</b> Guess the names of philosophers and famous personalities based on the clues provided.\n\n"
            f"✨ <b>How to Play:</b>\n"
            f"1️⃣ Characters will appear in the chat with a hint and an image.\n"
            f"2️⃣ Type their name to guess — no commands needed!\n"
            f"3️⃣ Earn points based on the character's rarity.\n\n"
            f"🏆 <b>Rarities & Points:</b>\n"
            f"• Common: 10 points\n"
            f"• Rare: 25 points\n"
            f"• Epic: 50 points\n"
            f"• Legendary: 100 points\n\n"
            f"Use <b>/help</b> to see all available commands. Good luck, and have fun guessing!"
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
            f"• /stats - View bot statistics (Owner only)\n"
            f"• /levels - View the leaderboard\n"
            f"• /profile - View your profile\n"
            f"• /addsudo - Add a sudo user (Owner only)\n"
            f"• /broadcast - Broadcast a message (Sudo/Admin only)\n"
            f"• /upload - Upload a new character\n"
            f"✨ Guess names directly in chat to earn points!"
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/techpiro"))

        bot.send_message(message.chat.id, help_message, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        logging.error(f"Error in /help command: {e}")
        bot.reply_to(message, "❌ An error occurred while displaying the help menu.")

@bot.message_handler(commands=['levels'])
def show_levels(message):
    """Displays the leaderboard with top users and their titles."""
    try:
        top_users = users_collection.find().sort("coins", -1).limit(10)  # Fetch top 10 users
        leaderboard = "<b>🏆 Leaderboard - Top Players 🏆</b>\n\n"

        for i, user in enumerate(top_users, 1):
            profile_name = user.get('profile_name', 'Unknown')
            xp = user.get('xp', 0)
            level = calculate_level(xp)
            title = get_title(level)
            leaderboard += f"{i}. <b>{profile_name}</b> - {title}\n"

        if leaderboard.strip() == "":
            bot.send_message(message.chat.id, "❌ No users found in the leaderboard.")
        else:
            bot.send_message(message.chat.id, leaderboard, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error in /levels command: {e}")
        bot.reply_to(message, "❌ Failed to fetch leaderboard. Please try again later.")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    """Displays bot statistics (Owner only)."""
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "❌ Only the bot owner can use this command.")
        return

    try:
        user_count = users_collection.count_documents({})
        character_count = characters_collection.count_documents({})
        chat_count = chats_collection.count_documents({})

        stats_message = (
            f"📊 <b>Bot Statistics</b>\n"
            f"👤 Total Users: {user_count}\n"
            f"📚 Total Characters: {character_count}\n"
            f"💬 Total Chats: {chat_count}"
        )
        bot.send_message(message.chat.id, stats_message, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error fetching stats: {e}")
        bot.reply_to(message, "❌ Failed to fetch stats.")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    """Uploads a new character."""
    try:
        parts = message.text.split(" ", 2)
        if len(parts) < 3:
            bot.reply_to(message, "❌ Usage: /upload <image_url> <character_name>")
            return

        image_url = parts[1].strip()
        character_name = parts[2].strip()

        if not image_url.startswith("http"):
            bot.reply_to(message, "❌ Invalid image URL. Please provide a valid link.")
            return

        new_character = {
            "name": character_name,
            "image_url": image_url,
            "rarity": auto_assign_rarity(),
            "created_at": datetime.utcnow()
        }
        characters_collection.insert_one(new_character)

        bot.reply_to(
            message,
            f"✅ Character uploaded successfully:\n"
            f"📸 <b>Image:</b> {image_url}\n"
            f"👤 <b>Name:</b> {character_name}",
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Error uploading character: {e}")
        bot.reply_to(message, "❌ Failed to upload the character. Please try again.")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    """Displays the user's profile."""
    try:
        user_id = message.from_user.id
        user = users_collection.find_one({'user_id': user_id})

        if not user:
            bot.reply_to(message, "❌ You don't have a profile yet. Use /start to create one.")
            return

        xp = user.get('xp', 0)
        level = calculate_level(xp)
        title = get_title(level)
        coins = user.get('coins', 0)
        correct_guesses = user.get('correct_guesses', 0)
        streak = user.get('streak', 0)
        inventory = user.get('inventory', [])
        last_bonus = user.get('last_bonus', None)

        last_bonus_text = (
            f"{datetime.fromtimestamp(last_bonus).strftime('%Y-%m-%d %H:%M:%S')}" if last_bonus else "Never"
        )
        inventory_text = ", ".join(inventory) if inventory else "Empty"

        profile_message = (
            f"👤 <b>Your Profile</b>\n\n"
            f"🏅 <b>Title:</b> {title}\n"
            f"✨ <b>Level:</b> {level} (XP: {xp})\n"
            f"💰 <b>Coins:</b> {coins}\n"
            f"🎯 <b>Correct Guesses:</b> {correct_guesses}\n"
            f"🔥 <b>Streak:</b> {streak} days\n"
            f"🎒 <b>Inventory:</b> {inventory_text}\n"
            f"⏰ <b>Last Bonus Claimed:</b> {last_bonus_text}"
        )

        bot.send_message(message.chat.id, profile_message, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error in /profile command: {e}")
        bot.reply_to(message, "❌ An error occurred while fetching your profile.")

@bot.message_handler(commands=['addsudo'])
def add_sudo(message):
    """Adds a new sudo user."""
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "❌ Only the bot owner can use this command.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Usage: /addsudo <user_id>")
            return
        
        sudo_user_id = int(parts[1])
        sudo_users_collection.update_one(
            {'user_id': sudo_user_id},
            {'$set': {'user_id': sudo_user_id}},
            upsert=True
        )
        bot.reply_to(message, f"✅ User with ID {sudo_user_id} has been added as a sudo user.")
    except Exception as e:
        logging.error(f"Error adding sudo user: {e}")
        bot.reply_to(message, "❌ Failed to add sudo user.")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    """Broadcasts a message to all chats."""
    if not is_sudo_user(message.from_user.id):
        bot.reply_to(message, "❌ Only sudo users or the owner can use this command.")
        return
    
    try:
        text = message.text[len('/broadcast '):].strip()
        if not text:
            bot.reply_to(message, "❌ Usage: /broadcast <message>")
            return
        
        chats = chats_collection.find()
        for chat in chats:
            try:
                bot.send_message(chat['chat_id'], text)
            except Exception as e:
                logging.error(f"Error sending broadcast to chat {chat['chat_id']}: {e}")
        bot.reply_to(message, "✅ Broadcast sent successfully.")
    except Exception as e:
        logging.error(f"Error broadcasting message: {e}")
        bot.reply_to(message, "❌ Failed to send broadcast.")

@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def handle_message(message):
    """Handles general messages and manages guessing games."""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        user_text = message.text.strip().lower()

        # Check if there's an active game in the chat
        if chat_id in active_games:
            character = active_games[chat_id]
            character_words = character['name'].lower().split()  # Split the character's name into words

            # Check if the user's input matches any word in the character's name
            if any(word in character_words for word in user_text.split()):
                # Reward the user for a correct guess
                reward_user(user_id, chat_id, character)

                # Remove the completed character
                del active_games[chat_id]

                # Immediately start a new character game
                start_new_character_game(chat_id)
            else:
                bot.reply_to(message, "❌ Incorrect! Try again.")
        else:
            # Increment message count and start a new game if threshold is reached
            if increment_message_count(chat_id):
                start_new_character_game(chat_id)
    except Exception as e:
        logging.error(f"Error handling message: {e}")

# Start bot polling
try:
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
except Exception as e:
    logging.error(f"Error during bot polling: {e}")
