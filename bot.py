import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAF_vFaCjkktmBLisSvN5SarlfH8OdWCS3k"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "YOUR_MONGO_DB_URI"
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
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character
current_character = None
global_message_count = 0  # Global counter for messages in all chats

# Titles and ranks based on achievements
TITLES = {
    'newbie': {'guesses': 0, 'title': 'Newbie'},
    'beginner': {'guesses': 10, 'title': 'Beginner'},
    'intermediate': {'guesses': 50, 'title': 'Intermediate'},
    'pro': {'guesses': 100, 'title': 'Pro Guesser'},
    'legendary': {'guesses': 500, 'title': 'Legendary Guesser'}
}

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

def get_user_rank(guesses):
    for rank, data in TITLES.items():
        if guesses >= data['guesses']:
            title = data['title']
    return title

# Command Handlers

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    # Fetch or create user data
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.full_name
        update_user_data(user_id, {'profile': profile_name})

    # Custom welcome message with @TechPiro mention and help included
    welcome_message = """
🎮 **Welcome to Philo Game!**
🛠️ Bot created by: @TechPiro

Here are the available commands to help you get started:
- /bonus - Claim your daily reward of coins every 24 hours.
- /profile - View your profile including your stats.
- /harem - Check out the characters you've collected, grouped by rarity.
- /leaderboard - See the top players with the most coins.
- /topcoins - See the top players with the highest coins.
- /upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only).
- /delete <character_id> - Delete a character (Owner only).
- /gift <user_id> <character_id> - Gift a character to another user.
- /sendcoins <user_id> <amount> - Send coins to another user.
- /stats - View bot statistics (Owner only).
    
Start playing now and guess the anime characters to earn coins!
"""
    bot.send_message(message.chat.id, welcome_message, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available Commands:
/bonus - Claim your daily reward (50,000 coins every 24 hours)
/profile - View your profile
/harem - View your collected characters (grouped by rarity)
/leaderboard - Show the top 10 fastest guessers
/topcoins - Show the top 10 users with the highest coins
/upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only)
/delete <character_id> - Delete a character (Owner only)
/gift <user_id> <character_id> - Gift a character to another user
/sendcoins <user_id> <amount> - Send coins to another user
/stats - Show bot statistics (Owner only)
"""
    bot.reply_to(message, help_message)

@bot.message_handler(commands=['gift'])
def gift_character(message):
    try:
        _, target_user_id_str, character_id_str = message.text.split(maxsplit=2)
        target_user_id = int(target_user_id_str)
        character_id = int(character_id_str)

        # Fetch sender and target user data
        sender_id = message.from_user.id
        sender_data = get_user_data(sender_id)
        target_data = get_user_data(target_user_id)

        # Find character in sender's inventory
        character = next((char for char in sender_data['inventory'] if char['id'] == character_id), None)
        if character:
            # Transfer character from sender to target
            sender_data['inventory'].remove(character)
            target_data['inventory'].append(character)
            update_user_data(sender_id, {'inventory': sender_data['inventory']})
            update_user_data(target_user_id, {'inventory': target_data['inventory']})
            
            bot.reply_to(message, f"🎁 You have successfully gifted {character['character_name']} to {target_data['profile']}!")
        else:
            bot.reply_to(message, "❌ Character not found in your inventory.")
    except (ValueError, IndexError):
        bot.reply_to(message, "Usage: /gift <user_id> <character_id>")

@bot.message_handler(commands=['sendcoins'])
def send_coins(message):
    try:
        _, target_user_id_str, amount_str = message.text.split(maxsplit=2)
        target_user_id = int(target_user_id_str)
        amount = int(amount_str)

        sender_id = message.from_user.id
        sender_data = get_user_data(sender_id)
        target_data = get_user_data(target_user_id)

        if sender_data['coins'] >= amount:
            sender_data['coins'] -= amount
            target_data['coins'] += amount
            update_user_data(sender_id, {'coins': sender_data['coins']})
            update_user_data(target_user_id, {'coins': target_data['coins']})
            bot.reply_to(message, f"💸 You have successfully sent {amount} coins to {target_data['profile']}!")
        else:
            bot.reply_to(message, "❌ You do not have enough coins.")
    except (ValueError, IndexError):
        bot.reply_to(message, "Usage: /sendcoins <user_id> <amount>")

@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    # Top 10 fastest guessers
    users = users_collection.find().sort('correct_guesses', -1).limit(10)
    leaderboard_message = "🏆 **Top 10 Fastest Guessers**:\n\n"
    for rank, user in enumerate(users, start=1):
        leaderboard_message += f"{rank}. [{user['profile']}](tg://user?id={user['user_id']}): {user['correct_guesses']} correct guesses\n"
    bot.reply_to(message, leaderboard_message, parse_mode="Markdown")

@bot.message_handler(commands=['topcoins'])
def show_topcoins(message):
    # Top 10 users with highest coins
    users = users_collection.find().sort('coins', -1).limit(10)
    topcoins_message = "🏆 **Top 10 Users with Highest Coins**:\n\n"
    for rank, user in enumerate(users, start=1):
        topcoins_message += f"{rank}. [{user['profile']}](tg://user?id={user['user_id']}): {user['coins']} coins\n"
    bot.reply_to(message, topcoins_message, parse_mode="Markdown")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    user_rank = get_user_rank(user['correct_guesses'])
    profile_message = (
        f"Profile\nCoins: {user['coins']}\nCorrect Guesses: {user['correct_guesses']}\n"
        f"Streak: {user['streak']}\nTitle: {user_rank}\nInventory: {len(user['inventory'])} characters"
    )
    bot.reply_to(message, profile_message)

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
