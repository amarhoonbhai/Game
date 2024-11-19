import os
import random
from datetime import datetime, timedelta
from pymongo import MongoClient, errors
from telebot import TeleBot, types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))
CHARACTER_CHANNEL_ID = int(os.getenv("CHARACTER_CHANNEL_ID"))
BONUS_COINS = int(os.getenv("BONUS_COINS"))
STREAK_BONUS_COINS = int(os.getenv("STREAK_BONUS_COINS"))
COINS_PER_GUESS = int(os.getenv("COINS_PER_GUESS"))
XP_PER_GUESS = 10  # XP gained per correct guess
XP_THRESHOLD = 100  # XP needed for each level
MESSAGE_THRESHOLD = int(os.getenv("MESSAGE_THRESHOLD"))
TOP_LEADERBOARD_LIMIT = int(os.getenv("TOP_LEADERBOARD_LIMIT"))

# Initialize bot and MongoDB
bot = TeleBot(API_TOKEN)

try:
    client = MongoClient(MONGO_URI)
    db = client['philo_game']
    users_collection = db['users']
    characters_collection = db['characters']
    sudo_users_collection = db['sudo_users']
    chats_collection = db['chats']  # Collection to track chats and groups for broadcasting
    print("✅ Connected to MongoDB successfully.")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# Track messages and character
current_character = None
global_message_count = 0

# Utility Functions
def get_user_data(user_id):
    user = users_collection.find_one_and_update(
        {'user_id': user_id},
        {'$setOnInsert': {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'xp': 0,
            'level': 1,
            'inventory': [],
            'last_bonus': None,
            'streak': 0,
            'profile_name': ""
        }},
        upsert=True,
        return_document=True
    )
    return user

def update_user_data(user_id, update_data):
    try:
        users_collection.update_one({'user_id': user_id}, {'$set': update_data})
    except errors.PyMongoError as e:
        print(f"Failed to update user data: {e}")

def find_user_by_username(username):
    return users_collection.find_one({"profile_name": username})

def assign_rarity():
    return random.choices(['Common', 'Rare', 'Epic', 'Legendary'], weights=[60, 25, 10, 5])[0]

def fetch_new_character():
    try:
        characters = list(characters_collection.find())
        return random.choice(characters) if characters else None
    except errors.PyMongoError as e:
        print(f"Error fetching character: {e}")
        return None

def calculate_level(xp):
    return (xp // XP_THRESHOLD) + 1

def is_sudo_user(user_id):
    return user_id == BOT_OWNER_ID or sudo_users_collection.find_one({"user_id": user_id}) is not None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.chat.type in ['group', 'supergroup']:
        chats_collection.update_one({'chat_id': chat_id}, {'$set': {'chat_id': chat_id}}, upsert=True)
    
    user = get_user_data(user_id)
    user_name = message.from_user.full_name
    update_user_data(user_id, {'profile_name': user_name})
    bot.reply_to(message, f"🎉 Welcome to Philo Game, {user_name}! 🎮 Use /help to see available commands.")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
/start - Welcome message and profile creation
/bonus - Claim daily bonus coins
/profile - View your stats and game progress
/levels - Show top players by coins
/stats - Show bot statistics (Owner only)
/upload - Upload a new character (Admin and Sudo only)
/addsudo - Add a sudo user (Owner only)
/broadcast - Broadcast a message to all chats (Owner only)
/gift - Gift coins to another player by username or @mention
"""
    bot.reply_to(message, help_message)

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    now = datetime.now()

    if user['last_bonus']:
        time_since_bonus = now - user['last_bonus']
        if time_since_bonus < timedelta(days=1):
            time_left = timedelta(days=1) - time_since_bonus
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            bot.reply_to(message, f"⏳ Come back in {hours}h {minutes}m for your next bonus!")
            return

    new_coins = user['coins'] + BONUS_COINS + (user['streak'] * STREAK_BONUS_COINS)
    update_user_data(user_id, {
        'coins': new_coins,
        'last_bonus': now,
        'streak': user['streak'] + 1
    })
    bot.reply_to(message, f"💰 You received {BONUS_COINS} coins and a streak bonus! Total coins: {new_coins}.")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    xp = user.get('xp', 0)
    level = calculate_level(xp)

    if level != user.get('level', 1):
        update_user_data(user_id, {'level': level})

    profile_text = (
        f"👤 <b>Profile of {user['profile_name']}</b>\n"
        f"💰 <b>Coins:</b> {user['coins']}\n"
        f"🎯 <b>Correct Guesses:</b> {user['correct_guesses']}\n"
        f"🔥 <b>Streak:</b> {user['streak']} days\n"
        f"🌟 <b>Level:</b> {level}\n"
        f"📈 <b>XP:</b> {xp} / {XP_THRESHOLD} for next level\n"
    )
    bot.reply_to(message, profile_text, parse_mode='HTML')

@bot.message_handler(commands=['levels'])
def show_levels(message):
    top_users = users_collection.find().sort("coins", -1).limit(TOP_LEADERBOARD_LIMIT)
    leaderboard = "🏆 <b>Top Players by Coins</b> 🏆\n\n"
    for i, user in enumerate(top_users, 1):
        leaderboard += f"{i}. {user['profile_name']} - {user['coins']} coins\n"
    bot.reply_to(message, leaderboard, parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id == BOT_OWNER_ID:
        total_users = users_collection.count_documents({})
        total_characters = characters_collection.count_documents({})
        bot.reply_to(
            message,
            f"📊 Bot Stats:\n👥 Total Users: {total_users}\n🎭 Characters: {total_characters}"
        )
    else:
        bot.reply_to(message, "🚫 You don't have permission to use this command.")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id == BOT_OWNER_ID:
        msg_text = message.text.split(maxsplit=1)
        if len(msg_text) < 2:
            bot.reply_to(message, "Usage: /broadcast <message>")
            return
        
        broadcast_text = msg_text[1]
        success_count = 0
        fail_count = 0
        
        try:
            all_chats = chats_collection.find()
            for chat in all_chats:
                try:
                    bot.send_message(chat['chat_id'], broadcast_text)
                    success_count += 1
                except Exception as e:
                    print(f"Failed to send message to chat {chat['chat_id']}: {e}")
                    fail_count += 1
            
            bot.reply_to(message, f"✅ Broadcast completed! Success: {success_count}, Failed: {fail_count}")
        except errors.PyMongoError as e:
            bot.reply_to(message, f"🚫 Failed to retrieve chats for broadcast: {e}")
    else:
        bot.reply_to(message, "🚫 You don't have permission to use this command.")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    user_id = message.from_user.id
    if is_sudo_user(user_id):
        msg_parts = message.text.split()
        if len(msg_parts) >= 3:
            image_url = msg_parts[1]
            character_name = " ".join(msg_parts[2:])
            characters_collection.insert_one({
                'image_url': image_url,
                'character_name': character_name,
                'rarity': assign_rarity()
            })
            bot.reply_to(message, "✅ Character uploaded successfully!")
        else:
            bot.reply_to(message, "Usage: /upload <image_url> <character_name>")
    else:
        bot.reply_to(message, "🚫 You don't have permission to use this command.")

@bot.message_handler(commands=['addsudo'])
def add_sudo(message):
    user_id = message.from_user.id
    if user_id == BOT_OWNER_ID:
        try:
            _, sudo_id = message.text.split()
            sudo_id = int(sudo_id)
            sudo_users_collection.update_one(
                {'user_id': sudo_id},
                {'$set': {'user_id': sudo_id}},
                upsert=True
            )
            bot.reply_to(message, f"✅ User {sudo_id} has been added as a sudo user.")
        except ValueError:
            bot.reply_to(message, "Usage: /addsudo <user_id>")
    else:
        bot.reply_to(message, "🚫 You don't have permission to use this command.")

@bot.message_handler(commands=['gift'])
def gift_coins(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    msg_parts = message.text.split()

    if len(msg_parts) < 3:
        bot.reply_to(message, "Usage: /gift <username or @mention> <amount>")
        return

    recipient_identifier = msg_parts[1]
    try:
        amount = int(msg_parts[2])
    except ValueError:
        bot.reply_to(message, "The amount must be a number.")
        return

    if amount <= 0:
        bot.reply_to(message, "Please specify a positive amount.")
        return

    if user['coins'] < amount:
        bot.reply_to(message, "You don't have enough coins to complete this gift.")
        return

    # Check if recipient is by username or by mention
    if recipient_identifier.startswith('@'):
        recipient_profile_name = recipient_identifier[1:]
        recipient = find_user_by_username(recipient_profile_name)
    else:
        recipient = find_user_by_username(recipient_identifier)

    if not recipient:
        bot.reply_to(message, "Recipient not found. Please ensure the username or mention is correct.")
        return

    # Update coins for sender and recipient
    update_user_data(user_id, {'coins': user['coins'] - amount})
    update_user_data(recipient['user_id'], {'coins': recipient['coins'] + amount})

    bot.reply_to(
        message,
        f"🎁 You have gifted {amount} coins to {recipient['profile_name']}!"
    )

# Start bot polling
bot.infinity_polling(timeout=60, long_polling_timeout=60)
