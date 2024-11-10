import telebot
import random
import time
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bot configuration (replace with actual values)
API_TOKEN = "7579121046:AAElA71FDBxPgZRUuTY0GdyTdEsTj1b8oxk"
BOT_OWNER_ID = 7222795580
CHANNEL_ID = -1002438449944

# MongoDB setup
try:
    MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']
    users_collection = db['users']
    characters_collection = db['characters']
    print("✅ Connected to MongoDB")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# Bot setup
bot = telebot.TeleBot(API_TOKEN)

# Game settings
BONUS_COINS = 5000
COINS_PER_GUESS = 50
STREAK_BONUS_COINS = 1000
MESSAGE_THRESHOLD = 5
RARITY_LEVELS = {
    'Common': '⭐ Common',
    'Rare': '🌟 Rare',
    'Epic': '💎 Epic',
    'Legendary': '✨ Legendary'
}
RARITY_WEIGHTS = [60, 25, 10, 5]

# Captions for sending characters and correct guesses
character_captions = [
    "🕵️‍♂️ Who's this mysterious figure? Any guesses?",
    "🎭 A familiar face appears! Can you name them?",
    "🌌 Look who’s here! Think you know them?",
    "👀 Do you recognize this iconic character?",
    "🧩 Guess the name and earn your reward!",
]
correct_guess_captions = [
    "🎉 Amazing! You've nailed it!",
    "🏆 Well done! You've guessed it right!",
    "👏 You're on fire! Another correct guess!",
    "🔥 Incredible! You recognized the character!",
    "✨ Another victory for you! Keep going!",
]

# Global variables
current_character = None
global_message_count = 0

# Helper Functions
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if not user:
        user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'inventory': [],
            'last_bonus': None,
            'streak': 0,
            'level': 1
        }
        users_collection.insert_one(user)
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    characters = list(characters_collection.find())
    return random.choice(characters) if characters else None

def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = f"{random.choice(character_captions)}\n\n👤 Name: ???\n🌟 Rarity: {rarity}\n🔍 Can you identify this character?"
        bot.send_photo(chat_id, current_character['image_url'], caption=caption)

def handle_correct_guess(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    new_coins = user['coins'] + COINS_PER_GUESS
    user['correct_guesses'] += 1
    user['streak'] += 1
    streak_bonus = STREAK_BONUS_COINS * user['streak']
    update_user_data(user_id, {
        'coins': new_coins + streak_bonus,
        'correct_guesses': user['correct_guesses'],
        'streak': user['streak'],
        'inventory': user['inventory'] + [current_character]
    })
    bot.reply_to(message, f"{random.choice(correct_guess_captions)}\n🎉 Congratulations! You earned {COINS_PER_GUESS + streak_bonus} coins!")

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🤖 Welcome! Type or guess character names and explore commands to start collecting!")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
<b>📜 Available Commands:</b>
/bonus - Claim daily bonus
/stats - Show bot stats
/profile - View your profile with current stats
/levels - Show the top users by coins
/upload <url> <name> - Upload a character (admin only)
/addsudo <user_id> - Add a sudo user (admin only)
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if user['last_bonus'] and datetime.now() - user['last_bonus'] < timedelta(days=1):
        bot.reply_to(message, "🕐 You've already claimed your bonus today! Come back tomorrow!")
    else:
        update_user_data(user_id, {'coins': user['coins'] + BONUS_COINS, 'last_bonus': datetime.now(), 'streak': user['streak'] + 1})
        bot.reply_to(message, f"💰 You've claimed {BONUS_COINS} coins as your daily bonus!")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    profile_msg = (
        f"👤 <b>Your Profile:</b>\n"
        f"💰 Coins: {user['coins']}\n"
        f"🏆 Level: {user['level']}\n"
        f"🔢 Correct Guesses: {user['correct_guesses']}\n"
        f"🔥 Streak: {user['streak']}\n"
    )
    bot.reply_to(message, profile_msg, parse_mode='HTML')

@bot.message_handler(commands=['levels'])
def show_levels(message):
    top_users = users_collection.find().sort('coins', -1).limit(10)
    leaderboard = "<b>🏅 Top Players by Coins:</b>\n\n"
    for idx, user in enumerate(top_users, 1):
        leaderboard += f"{idx}. 🆔 {user['user_id']} - 💰 {user['coins']} coins\n"
    bot.reply_to(message, leaderboard, parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def show_bot_stats(message):
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    bot.reply_to(message, f"📊 Bot Stats:\n👥 Users: {total_users}\n🎎 Characters: {total_characters}")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if message.from_user.id == BOT_OWNER_ID:
        try:
            _, url, name = message.text.split(maxsplit=2)
            rarity = assign_rarity()
            character = {
                'image_url': url,
                'character_name': name,
                'rarity': rarity
            }
            characters_collection.insert_one(character)
            bot.reply_to(message, f"📥 Character {name} uploaded successfully with {RARITY_LEVELS[rarity]} rarity!")
        except ValueError:
            bot.reply_to(message, "⚠️ Please provide both an image URL and a character name.")
    else:
        bot.reply_to(message, "🚫 You are not authorized to upload characters.")

@bot.message_handler(commands=['addsudo'])
def add_sudo(message):
    if message.from_user.id == BOT_OWNER_ID:
        try:
            _, user_id = message.text.split()
            user_id = int(user_id)
            bot.reply_to(message, f"✅ User {user_id} has been added as a sudo user!")
        except ValueError:
            bot.reply_to(message, "⚠️ Please provide a valid user ID.")
    else:
        bot.reply_to(message, "🚫 You are not authorized to add sudo users.")

# Character Guessing and Message Handler
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_character, global_message_count
    chat_id = message.chat.id
    user_guess = message.text.strip().lower() if message.text else ""

    if message.chat.type in ['group', 'supergroup']:
        global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(chat_id)
        global_message_count = 0

    if current_character and user_guess in current_character['character_name'].strip().lower():
        handle_correct_guess(message)
        send_character(chat_id)  # Immediately send the next character

# Resilient polling loop to restart the bot if it stops
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"⚠️ Bot crashed due to {e}. Restarting in 10 seconds...")
        time.sleep(10)  # Wait before restarting
