import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAHZdA0akQJpX4AiUvoo_xr93s7FDrfU9PA"
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

# Helper Functions
def get_user_data(user_id):
    """Fetch user data from MongoDB, or create a new entry if it doesn't exist."""
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
    """Update user data in MongoDB."""
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_character_data():
    """Fetch all character data from the characters collection."""
    return list(characters_collection.find())

def send_character(chat_id):
    """Send a character image and details to the chat."""
    global current_character
    characters = get_character_data()
    if characters:
        current_character = random.choice(characters)
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {current_character['rarity']}\n"
        )
        bot.send_photo(chat_id, current_character['image_url'], caption=caption)

def is_owner_or_sudo(user_id):
    """Check if the user is the bot owner or a sudo user."""
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS

# /profile command: Display user stats, including coins, correct guesses, and streak
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)

    profile_name = user['profile'] or "Anonymous"
    coins = user.get('coins', 0)
    correct_guesses = user.get('correct_guesses', 0)
    streak = user.get('streak', 0)
    inventory_size = len(user.get('inventory', []))

    profile_message = (
        f"👤 **Profile: {profile_name}**\n"
        f"💰 **Coins**: {coins}\n"
        f"✅ **Correct Guesses**: {correct_guesses}\n"
        f"🔥 **Streak**: {streak}\n"
        f"🎒 **Inventory**: {inventory_size} characters"
    )
    bot.reply_to(message, profile_message, parse_mode='Markdown')

# /inventory command: Display user's character collection, grouped by rarity
@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    inventory = user.get('inventory', [])

    if not inventory:
        bot.reply_to(message, "Your inventory is empty. Start guessing characters to collect them!")
    else:
        # Group characters by rarity
        inventory_by_rarity = {
            'Common': [],
            'Rare': [],
            'Epic': [],
            'Legendary': []
        }

        # Group and count characters by rarity
        for character in inventory:
            inventory_by_rarity[character['rarity']].append(character)

        inventory_message = f"🎒 **{user['profile']}**'s Character Collection:\n\n"
        for rarity, char_list in inventory_by_rarity.items():
            if char_list:
                inventory_message += f"🔹 **{RARITY_LEVELS[rarity]} {rarity} Characters**:\n"
                char_count = {}
                for char in char_list:
                    if char['character_name'] not in char_count:
                        char_count[char['character_name']] = 0
                    char_count[char['character_name']] += 1
                
                for char_name, count in char_count.items():
                    inventory_message += f"  - {char_name} ×{count}\n"
                inventory_message += "\n"

        bot.reply_to(message, inventory_message)

# /leaderboard command: Show the top 10 users with the most coins
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    top_users = users_collection.find().sort('coins', -1).limit(10)
    leaderboard_message = "🏆 **Top 10 Leaderboard**:\n\n"
    for rank, user in enumerate(top_users, start=1):
        profile_name = user['profile'] or "Anonymous"
        coins = user.get('coins', 0)
        leaderboard_message += f"{rank}. {profile_name}: {coins} coins\n"
    bot.reply_to(message, leaderboard_message)

# /stats command: Show bot statistics (total users, coins distributed, correct guesses)
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
    bot.reply_to(message, stats_message)

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
