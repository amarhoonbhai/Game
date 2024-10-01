import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAFX3SvFQ7rK4EWNQnW6Ugop6UBtDDsupjE"
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
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character
current_character = None
global_message_count = 0  # Global counter for messages in all chats

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

# Command Handlers

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    # Fetch or create user data
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.full_name
        update_user_data(user_id, {'profile': profile_name})

    # Custom welcome message with @TechPiro mention
    welcome_message = """
🎮 **Welcome to Philo Game!**
🛠️ Bot created by: @TechPiro

Here are the available commands to help you get started:
- /bonus - Claim your daily reward of coins every 24 hours.
- /profile - View your profile including your stats.
- /harem - Check out the characters you've collected, grouped by rarity.
- /leaderboard - See the top players with the most coins.
- /upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only).
- /delete <character_id> - Delete a character (Owner only).
- /stats - View bot statistics (Owner only).

Start playing now and guess the anime characters to earn coins!
"""
    bot.send_message(message.chat.id, welcome_message, parse_mode="Markdown")

@bot.message_handler(commands=['harem'])
def show_harem(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    inventory = user['inventory']

    if not inventory:
        bot.reply_to(message, "Your harem is empty. Start guessing characters to collect them!")
    else:
        inventory_by_rarity = {
            'Common': [],
            'Epic': [],
            'Legendary': [],
            'Mythical': []
        }

        # Group characters by rarity and remove duplicates
        unique_inventory = {}
        for character in inventory:
            key = (character['character_name'], character['rarity'], character['image_url'])
            if key in unique_inventory:
                unique_inventory[key] += 1
            else:
                unique_inventory[key] = 1

        # Display characters by rarity with images
        for rarity, emoji in RARITY_LEVELS.items():
            characters = [(k[0], k[2], v) for k, v in unique_inventory.items() if k[1] == rarity]
            if characters:
                bot.send_message(message.chat.id, f"🔹 **{emoji} {rarity} Characters**:", parse_mode="Markdown")
                for character_name, image_url, count in characters:
                    caption = f"{character_name} ×{count}"
                    bot.send_photo(message.chat.id, image_url, caption=caption)

@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    users = users_collection.find().sort('coins', -1).limit(10)
    leaderboard_message = "🏆 **Top 10 Leaderboard**:\n\n"
    for rank, user in enumerate(users, start=1):
        leaderboard_message += f"{rank}. **{user['profile']}**: {user['coins']} coins\n"
    
    bot.reply_to(message, leaderboard_message, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "❌ You are not authorized to view this information.")
        return

    total_users = users_collection.count_documents({})
    total_coins_distributed = sum([user['coins'] for user in users_collection.find()])
    total_correct_guesses = sum([user['correct_guesses'] for user in users_collection.find()])

    stats_message = (
        f"📊 **Bot Stats**:\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💰 Total Coins Distributed: {total_coins_distributed}\n"
        f"✅ Total Correct Guesses: {total_correct_guesses}"
    )
    bot.reply_to(message, stats_message, parse_mode='Markdown')

# Handle all types of messages and increment the message counter
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_guess = message.text.strip().lower() if message.text else ""

    global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(chat_id)
        global_message_count = 0

    if current_character:
        character_name = current_character['character_name'].strip().lower()
        if user_guess in character_name:
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
            bot.reply_to(message, f"🎉 Congratulations! You guessed correctly and earned {COINS_PER_GUESS} coins!\n"
                                  f"🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-guess streak!")
            send_character(chat_id)
        else:
            update_user_data(user_id, {'streak': 0})

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
