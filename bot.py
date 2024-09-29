import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAGZy2yFxZ4XJOKlYonLI4m2d3mZ5Vyj6V0"
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
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character
current_character = None
global_message_count = 0  # Global counter for messages in all chats

# Predefined Avatars List
PREDEFINED_AVATARS = [
    "https://example.com/avatar1.png",
    "https://example.com/avatar2.png",
    "https://example.com/avatar3.png"
]

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
            'profile': None,
            'avatar': None  # Adding avatar field
        }
        users_collection.insert_one(new_user)
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

def is_owner_or_sudo(user_id):
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS

# Command Handlers

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.full_name
        update_user_data(user_id, {'profile': profile_name})

    welcome_message = """
🎮 **Welcome to Philo Game!**
🛠️ Bot created by: @TechPiro

Here are the available commands to help you get started:
- /bonus - Claim your daily reward of coins every 24 hours.
- /profile - View your profile including your stats and avatar.
- /inventory - Check out the characters you've collected, grouped by rarity.
- /leaderboard - See the top players with the most coins.
- /upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only).
- /delete <character_id> - Delete a character (Owner only).
- /avatar - Customize your avatar from predefined options or upload your own.
"""
    bot.send_message(message.chat.id, welcome_message, parse_mode="Markdown")

@bot.message_handler(commands=['avatar'])
def avatar_customization(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)

    # Extracting avatar URL or choice from message
    try:
        command, avatar_choice = message.text.split(maxsplit=1)
    except ValueError:
        avatar_choice = None

    if avatar_choice and avatar_choice.startswith("http"):
        # User uploaded a custom avatar
        update_user_data(user_id, {'avatar': avatar_choice})
        bot.reply_to(message, "✅ Your avatar has been updated successfully!")
    elif avatar_choice and avatar_choice.isdigit():
        avatar_index = int(avatar_choice) - 1
        if 0 <= avatar_index < len(PREDEFINED_AVATARS):
            selected_avatar = PREDEFINED_AVATARS[avatar_index]
            update_user_data(user_id, {'avatar': selected_avatar})
            bot.reply_to(message, "✅ Your avatar has been updated successfully!")
        else:
            bot.reply_to(message, "❌ Invalid choice. Please select a valid avatar number.")
    else:
        # Display predefined avatar options
        avatar_list = "\n".join([f"{i+1}. [Avatar {i+1}]({PREDEFINED_AVATARS[i]})" for i in range(len(PREDEFINED_AVATARS))])
        avatar_message = (
            f"🎭 **Avatar Customization**:\n\n"
            f"Choose one of the following avatars by sending the number (1-{len(PREDEFINED_AVATARS)}):\n\n"
            f"{avatar_list}\n\n"
            f"Or, you can upload your own avatar by sending a direct image URL."
        )
        bot.send_message(message.chat.id, avatar_message, parse_mode="Markdown")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    avatar = user['avatar'] if user['avatar'] else "No avatar set."
    profile_message = (
        f"👤 **Profile**\n\n"
        f"Name: {user['profile']}\n"
        f"Coins: {user['coins']}\n"
        f"Correct Guesses: {user['correct_guesses']}\n"
        f"Streak: {user['streak']}\n"
        f"Inventory: {len(user['inventory'])} characters\n"
        f"Avatar: {avatar}\n"
    )
    bot.reply_to(message, profile_message)

@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    users = users_collection.find().sort('coins', -1).limit(10)
    leaderboard_message = "🏆 **Top 10 Leaderboard**:\n\n"
    for rank, user in enumerate(users, start=1):
        leaderboard_message += f"{rank}. {user['profile']}: {user['coins']} coins\n"
    
    bot.reply_to(message, leaderboard_message)

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
