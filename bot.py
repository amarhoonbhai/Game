import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from threading import Timer

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAHvMnEugexDxWso2lemjFLFIu5OkaJYcxM"
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

# Reminder system for claiming bonus
def send_bonus_reminder():
    now = datetime.now()
    users = users_collection.find()
    for user in users:
        if user['last_bonus']:
            last_bonus_time = datetime.fromisoformat(user['last_bonus'])
            if now - last_bonus_time >= BONUS_INTERVAL:
                try:
                    bot.send_message(user['user_id'], "⏰ Don't forget to claim your daily bonus using /bonus!")
                except:
                    continue  # In case the user blocks the bot or there is an error
    Timer(REMINDER_INTERVAL, send_bonus_reminder).start()

# Start the bonus reminder loop
send_bonus_reminder()

# /start Welcome Message with Developer Mention
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    # Fetch or create user data
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.full_name
        update_user_data(user_id, {'profile': profile_name})

    welcome_message = """
🎮 **Welcome to Philo Game!**
🛠️ Bot developed by [@TechPiro](https://t.me/TechPiro)

**Start playing now!** Here are some commands to help you get started:
- /bonus - Claim your daily reward of coins every 24 hours.
- /profile - View your profile including your stats.
- /inventory - Check out the characters you've collected, grouped by rarity.
- /leaderboard - See the top players with the most correct guesses.
- /topcoins - See the top players with the most coins.
- /gift @username <amount> - Gift coins to another user by their username.
- /upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only).
- /delete <character_id> - Delete a character (Owner only).
- /stats - View bot statistics (Owner only).

**Join the fun!** Guess anime characters to earn coins and collect unique characters!
"""
    bot.send_message(message.chat.id, welcome_message, parse_mode="Markdown")

# Updated /help command to list all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
💡 **Available Commands**:
/start - Welcome message and bot introduction.
/bonus - Claim your daily reward of coins (50,000 coins every 24 hours).
/profile - View your profile with your stats and streaks.
/inventory - View your collected characters, grouped by rarity.
/leaderboard - Show the top 10 users with the most correct guesses and their most collected character.
/topcoins - Show the top 10 users with the most coins.
/gift @username <amount> - Gift coins to another user by their username.
/upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only).
/delete <character_id> - Delete a character (Owner only).
/stats - View bot statistics (Owner only).
"""
    bot.reply_to(message, help_message, parse_mode="Markdown")

# Updated /leaderboard command
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    users = users_collection.find().sort('correct_guesses', -1).limit(10)
    leaderboard_message = "🏆 **Top 10 Leaderboard (Correct Guesses)**:\n\n"
    
    for rank, user in enumerate(users, start=1):
        # Get the user's most collected character by counting occurrences
        inventory = user.get('inventory', [])
        if inventory:
            # Group characters by name and find the most common
            character_counts = {}
            for character in inventory:
                character_name = character['character_name']
                if character_name in character_counts:
                    character_counts[character_name] += 1
                else:
                    character_counts[character_name] = 1
            # Find the most collected character
            most_collected_character = max(character_counts, key=character_counts.get)
        else:
            most_collected_character = "No characters collected"

        user_link = f"[{user['profile']}](tg://user?id={user['user_id']})"
        leaderboard_message += (
            f"{rank}. {user_link}: {user['correct_guesses']} correct guesses, "
            f"Most Collected Character: {most_collected_character}\n"
        )
    
    bot.reply_to(message, leaderboard_message, parse_mode='Markdown')

# New /topcoins command: show users with the highest coin count
@bot.message_handler(commands=['topcoins'])
def show_topcoins(message):
    users = users_collection.find().sort('coins', -1).limit(10)
    topcoins_message = "💰 **Top 10 Users by Coins**:\n\n"
    
    for rank, user in enumerate(users, start=1):
        user_link = f"[{user['profile']}](tg://user?id={user['user_id']})"
        topcoins_message += f"{rank}. {user_link}: {user['coins']} coins\n"
    
    bot.reply_to(message, topcoins_message, parse_mode='Markdown')

# New /gift command to gift coins to other users by username
@bot.message_handler(commands=['gift'])
def gift_coins(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    try:
        # Format: /gift @username <amount>
        _, recipient_username, amount_str = message.text.split(maxsplit=2)
        amount = int(amount_str)

        # Remove the '@' from the username
        if recipient_username.startswith('@'):
            recipient_username = recipient_username[1:]
    except ValueError:
        bot.reply_to(message, "❌ Format: /gift @username <amount>")
        return

    # Ensure the sender has enough coins to gift
    if user['coins'] < amount:
        bot.reply_to(message, "❌ You don't have enough coins to gift!")
        return

    # Check if the recipient exists in the database based on the username
    recipient = users_collection.find_one({'profile': recipient_username})
    if recipient is None:
        bot.reply_to(message, f"❌ User @{recipient_username} not found!")
        return

    # Update the sender and recipient's coins
    new_sender_coins = user['coins'] - amount
    new_recipient_coins = recipient['coins'] + amount
    update_user_data(user_id, {'coins': new_sender_coins})
    update_user_data(recipient['user_id'], {'coins': new_recipient_coins})

    # Notify both users
    bot.reply_to(message, f"🎁 You gifted {amount} coins to @{recipient_username}!")
    try:
        bot.send_message(recipient['user_id'], f"🎉 You received {amount} coins from @{user['profile']}!")
    except:
        pass  # In case the recipient blocks the bot or there is an error

# Updated /bonus command with claim reminder in mind
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    now = datetime.now()

    if user['last_bonus'] and now - datetime.fromisoformat(user['last_bonus']) < BONUS_INTERVAL:
        next_claim = datetime.fromisoformat(user['last_bonus']) + BONUS_INTERVAL
        remaining_time = next_claim - now
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"You can claim your next bonus in {hours_left} hours and {minutes_left} minutes.")
    else:
        new_coins = user['coins'] + BONUS_COINS
        update_user_data(user_id, {'coins': new_coins, 'last_bonus': now.isoformat()})
        bot.reply_to(message, f"🎉 You have received {BONUS_COINS} coins!")

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
