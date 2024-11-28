import os
import random
import logging
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

RARITY_LEVELS = [
    {"level": "Common", "emoji": "🌟"},
    {"level": "Rare", "emoji": "💎"},
    {"level": "Epic", "emoji": "🔥"},
    {"level": "Legendary", "emoji": "👑"}
]
RARITY_POINTS = {"Common": 10, "Rare": 25, "Epic": 50, "Legendary": 100}

# Initialize bot and MongoDB
bot = TeleBot(API_TOKEN)

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['anime_game']
    users_collection = db['users']
    characters_collection = db['characters']
    sudo_users_collection = db['sudo_users']
    active_games = {}
    logging.info("✅ Connected to MongoDB successfully.")
except errors.ServerSelectionTimeoutError as err:
    logging.error(f"❌ Could not connect to MongoDB: {err}")
    exit()

# Utility Functions
def to_custom_small_caps(text):
    """Formats text with the first word capitalized, and all other words in small caps."""
    small_caps_map = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
    }
    words = text.split()
    if not words:
        return text
    first_word = words[0].capitalize()
    small_caps_words = [
        ''.join(small_caps_map.get(c.lower(), c) for c in word)
        for word in words[1:]
    ]
    return ' '.join([first_word] + small_caps_words)

def get_rarity_emoji(rarity_name):
    for rarity in RARITY_LEVELS:
        if rarity["level"] == rarity_name:
            return rarity["emoji"]
    return "❓"

def is_owner(user_id):
    return user_id == BOT_OWNER_ID

def is_sudo_user(user_id):
    return is_owner(user_id) or sudo_users_collection.find_one({"user_id": user_id}) is not None

def calculate_level(xp):
    return min((xp // 100) + 1, 1000)

# Bot Commands
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Unknown"
    users_collection.update_one(
        {'user_id': user_id},
        {'$setOnInsert': {
            'user_id': user_id,
            'first_name': first_name,
            'coins': 0,
            'correct_guesses': 0,
            'xp': 0,
            'level': 1,
            'streak': 0,
            'joined_at': datetime.utcnow()
        }},
        upsert=True
    )
    welcome_message = (
        f"welcome to anime character guesser, {first_name}! 🎉\n\n"
        f"guess the names of famous anime characters from their images and rarity hints! 🎭\n\n"
        f"💡 use /help for more information!"
    )
    bot.send_message(
        message.chat.id,
        to_custom_small_caps(welcome_message),
        parse_mode='HTML'
    )

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = (
        f"🛠️ ʜᴇʟᴘ ᴍᴇɴᴜ 🛠️\n\n"
        f"📌 ᴄᴏᴍᴍᴀɴᴅs:\n"
        f"• /start - ꜱᴛᴀʀᴛ ᴛʜᴇ ɢᴀᴍᴇ 🎮\n"
        f"• /profile - ᴠɪᴇᴡ ʏᴏᴜʀ ᴘʀᴏғɪʟᴇ 👤\n"
        f"• /leaderboard - ᴛᴏᴘ ᴘʟᴀʏᴇʀs 🏆\n"
        f"• /bonus - ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ʙᴏɴᴜs 💰\n"
        f"• /upload - ᴜᴘʟᴏᴀᴅ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ (ᴏᴡɴᴇʀ ᴏɴʟʏ) 📸\n"
        f"• /stats - ᴠɪᴇᴡ ʙᴏᴛ sᴛᴀᴛs (ᴏᴡɴᴇʀ ᴏɴʟʏ) 📊\n"
        f"• /broadcast - ʙʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ (ᴏᴡɴᴇʀ ᴏɴʟʏ) 📢\n\n"
        f"💡 ᴛʏᴘᴇ ᴛʜᴇ ɴᴀᴍᴇ ᴏғ ᴛʜᴇ ᴀɴɪᴍᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ᴇᴀʀɴ ᴘᴏɪɴᴛs!"
    )
    bot.send_message(
        message.chat.id,
        to_custom_small_caps(help_message),
        parse_mode='HTML'
    )

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user = users_collection.find_one({'user_id': message.from_user.id})
    if not user:
        bot.reply_to(message, to_custom_small_caps("you don’t have a profile yet. use /start to create one!"))
        return
    xp = user['xp']
    level = calculate_level(xp)
    profile_message = (
        f"👤 your profile:\n\n"
        f"✨ name: {user['first_name']}\n"
        f"🏆 level: {level}\n"
        f"💰 coins: {user['coins']}\n"
        f"🔥 streak: {user['streak']} days\n"
        f"🎯 correct guesses: {user['correct_guesses']}"
    )
    bot.send_message(
        message.chat.id,
        to_custom_small_caps(profile_message),
        parse_mode='HTML'
    )

@bot.message_handler(commands=['bonus'])
def claim_daily_bonus(message):
    user_id = message.from_user.id
    user = users_collection.find_one({'user_id': user_id})
    if not user:
        bot.reply_to(message, to_custom_small_caps("you don’t have a profile yet. use /start to create one!"))
        return
    now = datetime.utcnow()
    last_bonus = user.get('last_bonus')
    if last_bonus and (now - last_bonus).days < 1:
        time_remaining = (last_bonus + timedelta(days=1)) - now
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        bot.reply_to(
            message,
            to_custom_small_caps(f"you’ve already claimed your bonus today! try again in {hours}h {minutes}m.")
        )
        return
    users_collection.update_one(
        {'user_id': user_id},
        {
            '$inc': {'coins': 50000},
            '$set': {'last_bonus': now}
        }
    )
    bot.send_message(
        message.chat.id,
        to_custom_small_caps("🎉 daily bonus claimed! you’ve received 50,000 coins! 💰"),
        parse_mode='HTML'
    )

@bot.message_handler(commands=['addsudo'])
def add_sudo(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, to_custom_small_caps("❌ only the owner can use this command!"))
        return
    try:
        user_id = int(message.text.split()[1])
        sudo_users_collection.update_one({'user_id': user_id}, {'$set': {'user_id': user_id}}, upsert=True)
        bot.reply_to(message, to_custom_small_caps(f"✅ user {user_id} has been added as a sudo user!"))
    except (IndexError, ValueError):
        bot.reply_to(message, to_custom_small_caps("❌ usage: /addsudo <user_id>"))

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, to_custom_small_caps("❌ only the owner can use this command!"))
        return
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    stats_message = (
        f"📊 bot stats:\n\n"
        f"👥 total users: {total_users}\n"
        f"📸 total characters: {total_characters}"
    )
    bot.send_message(
        message.chat.id,
        to_custom_small_caps(stats_message),
        parse_mode='HTML'
    )

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, to_custom_small_caps("❌ only the owner can use this command!"))
        return
    try:
        broadcast_text = message.text.split(' ', 1)[1]
        users = users_collection.find()
        for user in users:
            try:
                bot.send_message(user['user_id'], to_custom_small_caps(broadcast_text))
            except Exception as e:
                logging.error(f"Error sending broadcast to {user['user_id']}: {e}")
        bot.reply_to(message, to_custom_small_caps("✅ broadcast sent successfully!"))
    except IndexError:
        bot.reply_to(message, to_custom_small_caps("❌ usage: /broadcast <message>"))

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, to_custom_small_caps("❌ only the owner can use this command!"))
        return
    try:
        _, name, rarity, image_url = message.text.split(' ', 3)
        if rarity not in [r['level'] for r in RARITY_LEVELS]:
            bot.reply_to(message, to_custom_small_caps("❌ invalid rarity! use: common, rare, epic, legendary."))
            return
        characters_collection.insert_one({
            'name': name,
            'rarity': rarity.capitalize(),
            'image_url': image_url
        })
        bot.reply_to(message, to_custom_small_caps(f"✅ character {name} added successfully!"))
    except ValueError:
        bot.reply_to(message, to_custom_small_caps("❌ usage: /upload <name> <rarity> <image_url>"))

try:
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
except Exception as e:
    logging.error(f"Error during bot polling: {e}")
