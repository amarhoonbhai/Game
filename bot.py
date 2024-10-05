import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from threading import Timer

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAGdLmXgxvhFZweUOh0AA4_Mbmg_FXz54VY"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
try:
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    print("Connected to MongoDB")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    exit()  # Exit if connection fails

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 50000  # Bonus amount for daily claim
BONUS_INTERVAL = timedelta(days=1)  # Bonus claim interval (24 hours)

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

# Command Handlers

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.full_name or "Unknown User"
        username = message.from_user.username or None
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

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    profile_message = (
        f"👤 **Profile**\n\n"
        f"👤 Name: {user['profile'] or 'Unknown User'}\n"
        f"💰 Coins: {user['coins']}\n"
        f"✅ Correct Guesses: {user['correct_guesses']}\n"
        f"🔥 Streak: {user['streak']}\n"
        f"🎒 Inventory Size: {len(user['inventory'])} characters\n"
    )
    
    bot.reply_to(message, profile_message, parse_mode='Markdown')

@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    inventory = user['inventory']

    if not inventory:
        bot.reply_to(message, "Your inventory is empty. Start guessing characters to collect them!")
        return

    inventory_by_rarity = {
        'Common': [],
        'Rare': [],
        'Epic': [],
        'Legendary': []
    }

    # Group characters by rarity
    for character in inventory:
        rarity = character['rarity']
        inventory_by_rarity[rarity].append(character['character_name'])

    inventory_message = f"🎒 **{user['profile']}**'s Character Collection:\n\n"
    
    # Display characters by rarity
    for rarity, characters in inventory_by_rarity.items():
        if characters:
            inventory_message += f"🔹 **{rarity}** ({len(characters)} characters):\n"
            inventory_message += "\n".join([f"- {char}" for char in characters]) + "\n\n"
    
    bot.reply_to(message, inventory_message, parse_mode='Markdown')

# Updated /leaderboard
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    users = users_collection.find().sort('correct_guesses', -1).limit(10)
    leaderboard_message = "🏆 <b>Top 10 Leaderboard (Correct Guesses)</b>:\n\n"
    
    for rank, user in enumerate(users, start=1):
        first_name = user.get('profile', 'Unknown User')
        username = user.get('username', None)  # Get username if available
        character_count = len(user.get('inventory', []))  # Count of collected characters

        # Fallback for when username is not available
        if username:
            user_link = f'<a href="https://t.me/{username}"><b>{first_name}</b></a>'
        else:
            user_link = f'<b>{first_name}</b>'  # Display name without link

        leaderboard_message += f'{rank}. {user_link} ➾ <b>{character_count}</b> characters collected\n'
    
    bot.send_message(message.chat.id, leaderboard_message, parse_mode="HTML")

# New /topcoins command
@bot.message_handler(commands=['topcoins'])
def show_topcoins(message):
    users = users_collection.find().sort('coins', -1).limit(10)  # Sort by coins
    topcoins_message = "💰 <b>Top 10 Users by Coins</b>:\n\n"
    
    for rank, user in enumerate(users, start=1):
        first_name = user.get('profile', 'Unknown User')
        username = user.get('username', None)  # Get username if available
        character_count = len(user.get('inventory', []))  # Count of collected characters

        # Fallback for when username is not available
        if username:
            user_link = f'<a href="https://t.me/{username}"><b>{first_name}</b></a>'
        else:
            user_link = f'<b>{first_name}</b>'  # Display name without link

        topcoins_message += f'{rank}. {user_link} ➾ <b>{user["coins"]}</b> coins, {character_count} characters collected\n'
    
    bot.send_message(message.chat.id, topcoins_message, parse_mode="HTML")

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

# Start polling the bot
print("Bot is running...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
