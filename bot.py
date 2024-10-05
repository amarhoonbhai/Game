import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from threading import Timer

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7825167784:AAFdFpcNJUI6QFF6qTFbikKDx4xMzqmgt3A"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
try:
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    groups_collection = db['groups']  # Collection for group stats
    print("Connected to MongoDB")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    exit()  # Exit if connection fails

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 50000  # Bonus amount for daily claim
BONUS_INTERVAL = timedelta(days=1)  # Bonus claim interval (24 hours)
COINS_PER_GUESS = 50  # Coins for correct guesses
STREAK_BONUS_COINS = 1000  # Additional coins for continuing a streak
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character
current_character = None
global_message_count = 0  # Global counter for messages in all chats
REMINDER_INTERVAL = 3600  # Reminder interval in seconds (1 hour)

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
            'username': None
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_character_data():
    # Fetch all characters from the database
    characters = list(characters_collection.find())
    return characters

def fetch_new_character():
    characters = get_character_data()
    if characters:
        return random.choice(characters)
    else:
        return None

def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()

    if current_character:
        rarity = current_character['rarity']
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {current_character['rarity']}\n"
        )
        try:
            bot.send_photo(chat_id, current_character['image_url'], caption=caption)
            print(f"Character sent: {current_character['character_name']}")
        except Exception as e:
            print(f"Error sending character image: {e}")
            bot.send_message(chat_id, "❌ Unable to send character image.")
    else:
        print("No characters available in the database.")
        bot.send_message(chat_id, "❌ No characters available to send.")

# Command Handlers

# /start command to introduce the bot
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.full_name
        username = message.from_user.username  # Capture username
        update_user_data(user_id, {'profile': profile_name, 'username': username})

    welcome_message = """
🎮 **Welcome to Philo Game!**
🛠️ Bot developed by [@TechPiro](https://t.me/TechPiro)

**Start playing now!** Here are some commands to help you get started:
- /bonus - Claim your daily reward of coins every 24 hours.
- /profile - View your profile including your stats.
- /inventory - Check out the characters you've collected, grouped by rarity.
- /leaderboard - See the top players with the most correct guesses.
- /topcoins - See the top players with the most coins.
- /gift - Gift coins to another user by tagging them.
- /upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only).
- /delete <character_id> - Delete a character (Owner only).
- /stats - View bot statistics (Owner only).

**Join the fun!** Guess anime characters to earn coins and collect unique characters!
"""
    bot.send_message(message.chat.id, welcome_message, parse_mode="Markdown")

# /stats command to display bot statistics (Owner only)
@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "❌ You are not authorized to view this information.")
        return

    # User stats
    total_users = users_collection.count_documents({})
    total_coins_distributed = sum(user['coins'] for user in users_collection.find())
    total_correct_guesses = sum(user['correct_guesses'] for user in users_collection.find())

    # Group stats
    total_groups = groups_collection.count_documents({})
    total_group_messages = sum(group['message_count'] for group in groups_collection.find())

    stats_message = (
        f"📊 **Bot Stats**:\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💰 Total Coins Distributed: {total_coins_distributed}\n"
        f"✅ Total Correct Guesses: {total_correct_guesses}\n\n"
        f"👥 Total Groups: {total_groups}\n"
        f"💬 Total Group Messages: {total_group_messages}"
    )
    
    bot.send_message(message.chat.id, stats_message)

# Handle all types of messages and increment the message counter
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Check if the message is from a group or user chat
    if message.chat.type in ['group', 'supergroup']:
        # Group message, update the group data
        group_data = get_group_data(chat_id)
        new_message_count = group_data['message_count'] + 1
        update_group_data(chat_id, {'message_count': new_message_count})
    
    user_guess = message.text.strip().lower() if message.text else ""

    global_message_count += 1
    print(f"Message count: {global_message_count}")

    if global_message_count >= MESSAGE_THRESHOLD:
        print(f"Message threshold reached. Sending character to chat {chat_id}")
        send_character(chat_id)
        global_message_count = 0

    if current_character and user_guess:
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
print("Bot is running...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
