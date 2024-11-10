import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time

# Bot configuration
API_TOKEN = "7579121046:AAE5q2xhqw-A0ca-3xXvtrqv8SN1h8deKOs"
BOT_OWNER_ID = 7222795580
CHANNEL_ID = -1002438449944

# MongoDB Connection
try:
    MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']
    users_collection = db['users']
    characters_collection = db['characters']
    print("✅ MongoDB connected successfully.")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 5000
BONUS_INTERVAL = timedelta(days=1)
COINS_PER_GUESS = 50
LEVEL_UP_THRESHOLD = 5
MESSAGE_THRESHOLD = 5
RARITY_LEVELS = {'Common': '⭐', 'Rare': '🌟', 'Epic': '💎', 'Legendary': '✨'}
RARITY_WEIGHTS = [60, 25, 10, 5]
CAPTIONS = [
    "Amazing! You nailed it! 🎉",
    "Bravo! Another one for you! 💪",
    "You're on fire! 🔥",
    "Spot on! Keep going! 🌟",
    "Incredible guess! 🎈",
    "Wow! You have a keen eye! 👀",
    "You got it right again! 👏"
]

# Helper Functions
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'level': 1,
            'last_bonus': None,
            'streak': 0,
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def level_up_user(user):
    required_guesses = user['level'] * LEVEL_UP_THRESHOLD
    if user['correct_guesses'] >= required_guesses:
        user['level'] += 1
        update_user_data(user['user_id'], {'level': user['level']})
        return True
    return False

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    characters = list(characters_collection.find())
    return random.choice(characters) if characters else None

# Bot Commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
<b>📜 Available Commands:</b>

🎁 <b>Gameplay Commands:</b>
/bonus - Claim your daily bonus of 5000 coins.
/guess <character_name> - Guess the character’s name (automatic detection also enabled).

💼 <b>User Profile:</b>
/profile - Show your profile stats (coins, level, correct guesses).

🏆 <b>Leaderboards:</b>
/leaderboard - Show the top 10 users by coins.
/stats - Show overall bot stats (total users and characters).

⚙️ <b>Admin Commands:</b>
/upload <image_url> <character_name> - Upload a new character (Owner only).
/addsudo <user_id> - Add a user as sudo (Owner only).
/deletesudo <user_id> - Remove a user from sudo list (Owner only).
/status - Check if the bot is active.

ℹ️ <b>General:</b>
/help - Show this help message.

Enjoy the game and start collecting rare characters! 🎉
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    current_time = datetime.now()
    if user['last_bonus'] and (current_time - user['last_bonus']) < BONUS_INTERVAL:
        bot.reply_to(message, "You already claimed your bonus today! Try again tomorrow.")
        return
    user['coins'] += BONUS_COINS
    user['last_bonus'] = current_time
    update_user_data(user_id, {'coins': user['coins'], 'last_bonus': user['last_bonus']})
    bot.reply_to(message, f"🎉 You've claimed {BONUS_COINS} coins as a daily bonus!")

@bot.message_handler(commands=['stats'])
def show_bot_stats(message):
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    bot.reply_to(message, f"📊 Bot Stats:\nUsers: {total_users}\nCharacters: {total_characters}")

@bot.message_handler(commands=['status'])
def bot_status(message):
    bot.reply_to(message, "✅ Bot is active and ready!")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "❌ You don't have permission to use this command.")
        return
    try:
        args = message.text.split(" ")
        image_url = args[1]
        character_name = args[2]
        rarity = assign_rarity()
        characters_collection.insert_one({
            'image_url': image_url,
            'character_name': character_name,
            'rarity': rarity
        })
        bot.reply_to(message, f"Character '{character_name}' with rarity '{rarity}' has been uploaded.")
    except IndexError:
        bot.reply_to(message, "Usage: /upload <image_url> <character_name>")

def send_character(chat_id):
    character = fetch_new_character()
    if character:
        rarity = RARITY_LEVELS[character['rarity']]
        bot.send_photo(chat_id, character['image_url'], caption=f"Guess the character! Rarity: {rarity}")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_guess = message.text.strip().lower() if message.text else ""

    if message.chat.type in ['group', 'supergroup']:
        global_message_count = globals().get("global_message_count", 0) + 1
        globals()["global_message_count"] = global_message_count
        if global_message_count >= MESSAGE_THRESHOLD:
            send_character(chat_id)
            globals()["global_message_count"] = 0

    user = get_user_data(user_id)
    current_character = fetch_new_character()
    if current_character and user_guess:
        if user_guess in current_character['character_name'].lower():
            user['coins'] += COINS_PER_GUESS
            user['correct_guesses'] += 1
            update_user_data(user_id, {'coins': user['coins'], 'correct_guesses': user['correct_guesses']})
            level_up = level_up_user(user)
            caption = random.choice(CAPTIONS)
            if level_up:
                caption += f"\n🎉 You've leveled up to Level {user['level']}!"
            bot.reply_to(message, caption)
            send_character(chat_id)

# Restart bot if polling fails
while True:
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Error occurred: {e}. Restarting bot in 5 seconds...")
        time.sleep(5)
        
