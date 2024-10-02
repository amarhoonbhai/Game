import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAFNyNDPryICdr08Ojc3zSNz77JciNVZshI"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
client = MongoClient(MONGO_URI)
db = client['philo_grabber']  # Database name
users_collection = db['users']  # Collection for user data
characters_collection = db['characters']  # Collection for character data

# List of sudo users (user IDs)
SUDO_USERS = [7222795580, 6180999156]  # Add user IDs of sudo users here

bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 50000  # Bonus amount for daily claim
BONUS_INTERVAL = timedelta(days=1)  # Bonus claim interval (24 hours)
COINS_PER_GUESS = 50  # Coins for correct guesses
STREAK_BONUS_COINS = 1000  # Additional coins for continuing a streak
RARITY_LEVELS = {
    'Common': '🕊️',
    'Epic': '🌟',
    'Legendary': '🍷',
    'Mythical': '🔮'
}
RARITY_WEIGHTS = [60, 25, 10, 5]

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
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_user_by_username(username):
    user = users_collection.find_one({'profile': username})
    return user

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
    return character

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

# Command Handlers

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    # Calculate the title based on correct guesses
    if user['correct_guesses'] >= 500:
        title = 'Legendary Guesser'
    elif user['correct_guesses'] >= 100:
        title = 'Pro Guesser'
    elif user['correct_guesses'] >= 50:
        title = 'Intermediate'
    elif user['correct_guesses'] >= 10:
        title = 'Beginner'
    else:
        title = 'Newbie'
    
    # Display profile information
    profile_message = (
        f"👤 **Profile**\n"
        f"💰 Coins: {user['coins']}\n"
        f"✅ Correct Guesses: {user['correct_guesses']}\n"
        f"🔥 Streak: {user['streak']}\n"
        f"🏅 Title: {title}\n"
        f"🎒 Inventory: {len(user['inventory'])} characters"
    )
    bot.reply_to(message, profile_message, parse_mode="Markdown")

@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    users = users_collection.find().sort('correct_guesses', -1).limit(10)
    leaderboard_message = "🏆 **Top 10 Fastest Guessers**:\n\n"
    
    for rank, user in enumerate(users, start=1):
        user_mention = f"[{user['profile']}](tg://user?id={user['user_id']})"
        leaderboard_message += f"{rank}. {user_mention}: {user['correct_guesses']} correct guesses\n"
    
    bot.reply_to(message, leaderboard_message, parse_mode="Markdown")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_owner_or_sudo(message.from_user.id):
        bot.reply_to(message, "❌ You do not have permission to upload characters.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "Format: /upload <image_url> <character_name>")
        return

    rarity = assign_rarity()
    character = add_character(image_url, character_name, rarity)
    
    # Send confirmation to the user
    bot.send_message(CHANNEL_ID, f"New character uploaded: {character_name} (ID: {character['id']}, {RARITY_LEVELS[rarity]} {rarity})")
    bot.reply_to(message, f"✅ Character '{character_name}' uploaded successfully with ID {character['id']}!")

# Utility to check if user is bot owner or sudo user
def is_owner_or_sudo(user_id):
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
